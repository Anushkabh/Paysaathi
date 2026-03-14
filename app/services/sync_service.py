"""
Sync Service
-------------
Pulls data from the external accounting API and upserts it into the
local database.  Designed to be called on-demand or on a schedule.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.external.accounting_client import AccountingClient, AccountingAPIError
from app.models import Customer, Invoice, Payment
from app.models.invoice import InvoiceStatus
from app.schemas.schemas import SyncResult

logger = logging.getLogger(__name__)


class SyncService:
    def __init__(self, db: Session, client: AccountingClient | None = None):
        self.db = db
        self.client = client or AccountingClient()

    def sync_all(self) -> SyncResult:
        errors: list[str] = []
        customers_synced = self._sync_customers(errors)
        invoices_synced = self._sync_invoices(errors)
        payments_synced = self._sync_payments(errors)

        self._recompute_invoice_statuses()
        self.db.commit()

        result = SyncResult(
            customers_synced=customers_synced,
            invoices_synced=invoices_synced,
            payments_synced=payments_synced,
            errors=errors,
        )
        logger.info("Sync complete: %s", result)
        return result

    # ── Private helpers ──

    def _sync_customers(self, errors: list[str]) -> int:
        try:
            external = self.client.fetch_customers()
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

    def _sync_invoices(self, errors: list[str]) -> int:
        try:
            external = self.client.fetch_invoices()
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

    def _sync_payments(self, errors: list[str]) -> int:
        try:
            external = self.client.fetch_payments()
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
        After syncing payments, recalculate each invoice's status based on
        actual payment totals. This guards against stale status from the
        external system.
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
