from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class WebhookPayload(BaseModel):
    """
    Expected payload from the external accounting system's webhook.

    Example:
    {
      "event": "invoice.updated",
      "entity_type": "invoice",
      "entity_id": "INV-042",
      "timestamp": "2025-06-01T12:00:00Z",
      "data": { ... }         // optional snapshot of the changed entity
    }
    """
    event: str                            # e.g. "invoice.created", "payment.received"
    entity_type: str                      # "customer", "invoice", or "payment"
    entity_id: str
    timestamp: datetime
    data: Optional[dict] = None           # optional payload from external system


class WebhookResponse(BaseModel):
    received: bool
    event: str
    message: str
