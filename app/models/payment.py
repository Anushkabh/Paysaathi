from sqlalchemy import Column, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(String, primary_key=True)
    invoice_id = Column(String, ForeignKey("invoices.id"), nullable=False)
    amount = Column(Float, nullable=False)
    payment_date = Column(DateTime, nullable=False)
    method = Column(String, nullable=True)              # e.g. bank_transfer, card
    reference = Column(String, nullable=True)           # external reference/txn id
    synced_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    invoice = relationship("Invoice", back_populates="payments")
