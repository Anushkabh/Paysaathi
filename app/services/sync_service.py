"""
Sync Service
-------------
Pulls data from the external accounting API and upserts it into the
local database.  Supports full and incremental sync, with audit logging.

Sync strategies:
  - FULL:        Fetches everything. Used on first run or manual trigger.
  - INCREMENTAL: Fetches only records updated since last successful sync.
                 Falls back to full sync if no prior sync exists.
  - TARGETED:    Syncs a single entity by type + ID (used by webhooks).
"""
import logging
import time
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy.orm import Session

from app.external.accounting_client import AccountingClient, AccountingAPIError
from app.models import Customer, Invoice, Payment, SyncLog
from app.models.invoice import InvoiceStatus
from app.schemas.schemas import SyncResult

logger = logging.getLogger(__name__)


class SyncStrategy(str, Enum):
    FULL = "full"
    INCREMENTAL = "incremental"
    TARGETED = "targeted"


class SyncService:
    def __init__(self, db: Session, client: AccountingClient | None = None):
        self.db = db
        self.client = client or AccountingClient()

    # ── Public API ──

    def sync_all(self, trigger: str = "manual",
                 strategy: SyncStrategy = SyncStrategy.FULL) -> SyncResult:
        started = datetime.now(timezone.utc)
        t0 = time.monotonic()
        errors: list[str] = []

        since = None
        if strategy == SyncStrategy.INCREMENTAL:
            since = self._last_successful_sync_time()
            if since is None:
                logger.info("No prior sync found — falling back to full sync")
                strategy = SyncStrategy.FULL

        since_str = since.isoformat() if since else None

        customers_synced = self._sync_customers(errors, since=since_str)
        invoices_synced = self._sync_invoices(errors, since=since_str)
        payments_synced = self._sync_payments(errors, since=since_str)

        self._recompute_invoice_statuses()
        duration_ms = round((time.monotonic() - t0) * 1000, 2)

        status = "success" if not errors else "partial"
        if customers_synced == 0 and invoices_synced == 0 and payments_synced == 0 and errors:
            status = "failed"

        self._write_sync_log(
            trigger=trigger, status=status,
            customers_synced=customers_synced,
            invoices_synced=invoices_synced,
            payments_synced=payments_synced,
            errors=errors, duration_ms=duration_ms, started_at=started,
        )

        self.db.commit()

        result = SyncResult(
            customers_synced=customers_synced,
            invoices_synced=invoices_synced,
            payments_synced=payments_synced,
            errors=errors,
        )
        logger.info("Sync complete (%s, %s): %s in %.0fms",
                     strategy.value, trigger, result, duration_ms)
        return result

    def sync_entity(self, entity_type: str, entity_id: str,
                    trigger: str = "webhook") -> SyncResult:
        """Sync a single entity — used by webhook receiver."""
        started = datetime.now(timezone.utc)
        t0 = time.monotonic()
        errors: list[str] = []
        c, i, p = 0, 0, 0

        try:
            if entity_type == "customer":
                c = self._sync_customers(errors)
            elif entity_type == "invoice":
                i = self._sync_invoices(errors)
                self._recompute_invoice_statuses()
            elif entity_type == "payment":
                p = self._sync_payments(errors)
                self._recompute_invoice_statuses()
            else:
                errors.append(f"Unknown entity type: {entity_type}")
        except Exception as exc:
            errors.append(str(exc))

        duration_ms = round((time.monotonic() - t0) * 1000, 2)
        status = "success" if not errors else "partial"

        self._write_sync_log(
            trigger=trigger, status=status,
            customers_synced=c, invoices_synced=i, payments_synced=p,
            errors=errors, duration_ms=duration_ms, started_at=started,
        )
        self.db.commit()

        return SyncResult(
            customers_synced=c, invoices_synced=i,
            payments_synced=p, errors=errors,
        )

    # ── Private: data sync ──

    def _sync_customers(self, errors: list[str], since: str | None = None) -> int:
        try:
            external = self.client.fetch_customers(since=since)
        except AccountingAPIError as e:
            errors.append(f"customers: {e}")
            return 0

        count = 0
        for ext in external:
            existing = self.db.get(Customer, ext.id)
            if existing:
                existing.name = ext.name
                existing.email = ext.email
                existing.phone = ext.phone
                existing.credit_limit = ext.credit_limit or 0.0
                existing.synced_at = datetime.now(timezone.utc)
            else:
                self.db.add(Customer(
                    id=ext.id, name=ext.name, email=ext.email,
                    phone=ext.phone, credit_limit=ext.credit_limit or 0.0,
                ))
            count += 1
        return count

    def _sync_invoices(self, errors: list[str], since: str | None = None) -> int:
        try:
            external = self.client.fetch_invoices(since=since)
        except AccountingAPIError as e:
            errors.append(f"invoices: {e}")
            return 0

        count = 0
        for ext in external:
            existing = self.db.get(Invoice, ext.id)
            status = InvoiceStatus(ext.status)
            if existing:
                existing.amount = ext.amount
                existing.due_date = ext.due_date
                existing.issued_date = ext.issued_date
                existing.status = status
                existing.synced_at = datetime.now(timezone.utc)
            else:
                self.db.add(Invoice(
                    id=ext.id, customer_id=ext.customer_id,
                    amount=ext.amount, due_date=ext.due_date,
                    issued_date=ext.issued_date, status=status,
                ))
            count += 1
        return count

    def _sync_payments(self, errors: list[str], since: str | None = None) -> int:
        try:
            external = self.client.fetch_payments(since=since)
        except AccountingAPIError as e:
            errors.append(f"payments: {e}")
            return 0

        count = 0
        for ext in external:
            existing = self.db.get(Payment, ext.id)
            if existing:
                existing.amount = ext.amount
                existing.payment_date = ext.payment_date
                existing.method = ext.method
                existing.reference = ext.reference
                existing.synced_at = datetime.now(timezone.utc)
            else:
                self.db.add(Payment(
                    id=ext.id, invoice_id=ext.invoice_id,
                    amount=ext.amount, payment_date=ext.payment_date,
                    method=ext.method, reference=ext.reference,
                ))
            count += 1
        return count

    def _recompute_invoice_statuses(self):
        """
        Recalculate each invoice's status from actual payment totals.
        Guards against stale status from the external system.
        """
        invoices = self.db.query(Invoice).all()
        now = datetime.now(timezone.utc)

        for inv in invoices:
            paid = sum(p.amount for p in inv.payments)
            due = inv.due_date.replace(tzinfo=timezone.utc) if inv.due_date.tzinfo is None else inv.due_date
            if paid >= inv.amount:
                inv.status = InvoiceStatus.PAID
            elif due < now and paid < inv.amount:
                inv.status = InvoiceStatus.OVERDUE
            elif paid > 0:
                inv.status = InvoiceStatus.PARTIALLY_PAID
            else:
                inv.status = InvoiceStatus.PENDING

    # ── Private: audit log ──

    def _write_sync_log(self, trigger: str, status: str,
                        customers_synced: int, invoices_synced: int,
                        payments_synced: int, errors: list[str],
                        duration_ms: float, started_at: datetime):
        log = SyncLog(
            trigger=trigger, status=status,
            customers_synced=customers_synced,
            invoices_synced=invoices_synced,
            payments_synced=payments_synced,
            errors="; ".join(errors) if errors else None,
            duration_ms=duration_ms,
            started_at=started_at,
        )
        self.db.add(log)

    def _last_successful_sync_time(self) -> datetime | None:
        last = (
            self.db.query(SyncLog)
            .filter(SyncLog.status == "success")
            .order_by(SyncLog.completed_at.desc())
            .first()
        )
        return last.completed_at if last else None
