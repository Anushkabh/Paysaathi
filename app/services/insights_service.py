"""
Insights Service
-----------------
Computes financial insights: outstanding balances, overdue invoices,
aging analysis, and per-customer credit risk reports.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Customer, Invoice
from app.models.invoice import InvoiceStatus
from app.schemas.schemas import (
    CustomerBalance, OverdueInvoice, AgingBucket,
    CustomerCreditReport, CustomerOut,
)


def _aware(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware (SQLite stores naive datetimes)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


AGING_BUCKETS = [
    ("0-30 days", 0, 30),
    ("31-60 days", 31, 60),
    ("61-90 days", 61, 90),
    ("90+ days", 91, 999999),
]


class InsightsService:
    def __init__(self, db: Session):
        self.db = db

    # ── Outstanding balances per customer ──

    def get_customer_balances(self) -> list[CustomerBalance]:
        customers = self.db.query(Customer).all()
        results = []

        for cust in customers:
            total_invoiced = sum(inv.amount for inv in cust.invoices)
            total_paid = sum(
                p.amount
                for inv in cust.invoices
                for p in inv.payments
            )
            outstanding = total_invoiced - total_paid
            utilization = (
                (outstanding / cust.credit_limit * 100)
                if cust.credit_limit > 0 else 0.0
            )

            results.append(CustomerBalance(
                customer_id=cust.id,
                customer_name=cust.name,
                total_invoiced=round(total_invoiced, 2),
                total_paid=round(total_paid, 2),
                outstanding_balance=round(outstanding, 2),
                credit_limit=cust.credit_limit,
                credit_utilization_pct=round(utilization, 2),
            ))

        return results

    # ── Overdue invoices ──

    def get_overdue_invoices(self) -> list[OverdueInvoice]:
        now = datetime.now(timezone.utc)
        invoices = (
            self.db.query(Invoice)
            .filter(Invoice.due_date < now, Invoice.status != InvoiceStatus.PAID)
            .all()
        )
        results = []
        for inv in invoices:
            paid = sum(p.amount for p in inv.payments)
            customer = self.db.get(Customer, inv.customer_id)
            results.append(OverdueInvoice(
                invoice_id=inv.id,
                customer_id=inv.customer_id,
                customer_name=customer.name if customer else "Unknown",
                amount=inv.amount,
                amount_paid=round(paid, 2),
                balance_due=round(inv.amount - paid, 2),
                due_date=inv.due_date,
                days_overdue=(now - _aware(inv.due_date)).days,
            ))

        results.sort(key=lambda x: x.days_overdue, reverse=True)
        return results

    # ── Aging analysis ──

    def get_aging_report(self) -> list[AgingBucket]:
        now = datetime.now(timezone.utc)
        unpaid = (
            self.db.query(Invoice)
            .filter(Invoice.status != InvoiceStatus.PAID)
            .all()
        )

        buckets = {label: {"total": 0.0, "count": 0} for label, _, _ in AGING_BUCKETS}

        for inv in unpaid:
            paid = sum(p.amount for p in inv.payments)
            balance = inv.amount - paid
            if balance <= 0:
                continue

            age_days = (now - _aware(inv.due_date)).days if _aware(inv.due_date) < now else 0
            for label, lo, hi in AGING_BUCKETS:
                if lo <= age_days <= hi:
                    buckets[label]["total"] += balance
                    buckets[label]["count"] += 1
                    break

        return [
            AgingBucket(
                bucket=label,
                total_outstanding=round(buckets[label]["total"], 2),
                invoice_count=buckets[label]["count"],
            )
            for label, _, _ in AGING_BUCKETS
        ]

    # ── Per-customer credit report ──

    def get_customer_credit_report(self, customer_id: str) -> CustomerCreditReport | None:
        customer = self.db.get(Customer, customer_id)
        if not customer:
            return None

        now = datetime.now(timezone.utc)
        invoices = customer.invoices

        total_invoiced = sum(inv.amount for inv in invoices)
        total_paid = sum(p.amount for inv in invoices for p in inv.payments)
        outstanding = total_invoiced - total_paid

        # Overdue stats
        overdue_invs = [
            inv for inv in invoices
            if _aware(inv.due_date) < now and inv.status != InvoiceStatus.PAID
        ]
        overdue_amount = sum(
            inv.amount - sum(p.amount for p in inv.payments)
            for inv in overdue_invs
        )

        # Average days to pay (for paid invoices)
        days_list = []
        for inv in invoices:
            paid = sum(p.amount for p in inv.payments)
            if paid >= inv.amount and inv.payments:
                last_payment = max(inv.payments, key=lambda p: p.payment_date)
                delta = (_aware(last_payment.payment_date) - _aware(inv.issued_date)).days
                days_list.append(delta)
        avg_days = round(sum(days_list) / len(days_list), 1) if days_list else None

        # Aging breakdown for this customer
        aging = {label: {"total": 0.0, "count": 0} for label, _, _ in AGING_BUCKETS}
        for inv in invoices:
            if inv.status == InvoiceStatus.PAID:
                continue
            paid = sum(p.amount for p in inv.payments)
            balance = inv.amount - paid
            if balance <= 0:
                continue
            age_days = (now - _aware(inv.due_date)).days if _aware(inv.due_date) < now else 0
            for label, lo, hi in AGING_BUCKETS:
                if lo <= age_days <= hi:
                    aging[label]["total"] += balance
                    aging[label]["count"] += 1
                    break

        aging_breakdown = [
            AgingBucket(
                bucket=label,
                total_outstanding=round(aging[label]["total"], 2),
                invoice_count=aging[label]["count"],
            )
            for label, _, _ in AGING_BUCKETS
        ]

        # Risk scoring
        risk = self._compute_risk(outstanding, customer.credit_limit,
                                  len(overdue_invs), avg_days)

        return CustomerCreditReport(
            customer=CustomerOut.model_validate(customer),
            outstanding_balance=round(outstanding, 2),
            overdue_amount=round(overdue_amount, 2),
            overdue_invoice_count=len(overdue_invs),
            average_days_to_pay=avg_days,
            aging_breakdown=aging_breakdown,
            risk_level=risk,
        )

    @staticmethod
    def _compute_risk(outstanding: float, credit_limit: float,
                      overdue_count: int, avg_days: float | None) -> str:
        score = 0
        if credit_limit > 0 and outstanding / credit_limit > 0.8:
            score += 2
        elif credit_limit > 0 and outstanding / credit_limit > 0.5:
            score += 1

        if overdue_count >= 3:
            score += 2
        elif overdue_count >= 1:
            score += 1

        if avg_days and avg_days > 60:
            score += 1

        if score >= 3:
            return "HIGH"
        elif score >= 2:
            return "MEDIUM"
        return "LOW"
