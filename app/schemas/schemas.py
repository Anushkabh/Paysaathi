from pydantic import BaseModel
from datetime import datetime
from typing import Optional


# ── External API response shapes ──

class ExternalCustomer(BaseModel):
    id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    credit_limit: Optional[float] = 0.0


class ExternalInvoice(BaseModel):
    id: str
    customer_id: str
    amount: float
    due_date: datetime
    issued_date: datetime
    status: str


class ExternalPayment(BaseModel):
    id: str
    invoice_id: str
    amount: float
    payment_date: datetime
    method: Optional[str] = None
    reference: Optional[str] = None


# ── API response schemas ──

class CustomerOut(BaseModel):
    id: str
    name: str
    email: Optional[str]
    phone: Optional[str]
    credit_limit: float

    model_config = {"from_attributes": True}


class InvoiceOut(BaseModel):
    id: str
    customer_id: str
    amount: float
    due_date: datetime
    issued_date: datetime
    status: str

    model_config = {"from_attributes": True}


class PaymentOut(BaseModel):
    id: str
    invoice_id: str
    amount: float
    payment_date: datetime
    method: Optional[str]
    reference: Optional[str]

    model_config = {"from_attributes": True}


# ── Insight schemas ──

class CustomerBalance(BaseModel):
    customer_id: str
    customer_name: str
    total_invoiced: float
    total_paid: float
    outstanding_balance: float
    credit_limit: float
    credit_utilization_pct: float


class OverdueInvoice(BaseModel):
    invoice_id: str
    customer_id: str
    customer_name: str
    amount: float
    amount_paid: float
    balance_due: float
    due_date: datetime
    days_overdue: int


class AgingBucket(BaseModel):
    bucket: str               # e.g. "0-30 days", "31-60 days"
    total_outstanding: float
    invoice_count: int


class CustomerCreditReport(BaseModel):
    customer: CustomerOut
    outstanding_balance: float
    overdue_amount: float
    overdue_invoice_count: int
    average_days_to_pay: Optional[float]
    aging_breakdown: list[AgingBucket]
    risk_level: str            # LOW, MEDIUM, HIGH


class SyncResult(BaseModel):
    customers_synced: int
    invoices_synced: int
    payments_synced: int
    errors: list[str]
