from sqlalchemy import Column, String, Integer, DateTime, Float, Text
from datetime import datetime, timezone
import enum

from app.database import Base


class SyncLog(Base):
    """Tracks every sync run for auditability and incremental sync cursor."""
    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trigger = Column(String, nullable=False)       # "manual", "webhook", "scheduled"
    status = Column(String, nullable=False)         # "success", "partial", "failed"
    customers_synced = Column(Integer, default=0)
    invoices_synced = Column(Integer, default=0)
    payments_synced = Column(Integer, default=0)
    errors = Column(Text, nullable=True)
    duration_ms = Column(Float, nullable=True)
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
