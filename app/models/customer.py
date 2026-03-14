from sqlalchemy import Column, String, DateTime, Float
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(String, primary_key=True)              # external system ID
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    credit_limit = Column(Float, default=0.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
    synced_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    invoices = relationship("Invoice", back_populates="customer")
