from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum

from app.database import Base


class InvoiceStatus(str, enum.Enum):
    PENDING = "pending"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    OVERDUE = "overdue"


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    amount = Column(Float, nullable=False)
    due_date = Column(DateTime, nullable=False)
    issued_date = Column(DateTime, nullable=False)
    status = Column(SAEnum(InvoiceStatus), default=InvoiceStatus.PENDING)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    synced_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    customer = relationship("Customer", back_populates="invoices")
    payments = relationship("Payment", back_populates="invoice")
