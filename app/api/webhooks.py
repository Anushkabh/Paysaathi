"""
Webhook Receiver
-----------------
Receives push notifications from the external accounting system so we can
sync individual records in near-real-time instead of polling.

Security: validates the X-Webhook-Secret header against our configured secret.
In production, this would use HMAC signature verification on the raw body.
"""
import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.schemas.webhook import WebhookPayload, WebhookResponse
from app.services.sync_service import SyncService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

VALID_ENTITY_TYPES = {"customer", "invoice", "payment"}


def _verify_secret(x_webhook_secret: str = Header(...)):
    """Reject requests without a valid webhook secret."""
    if x_webhook_secret != settings.WEBHOOK_SECRET:
        logger.warning("Webhook rejected — invalid secret")
        raise HTTPException(status_code=401, detail="Invalid webhook secret")


@router.post("/accounting", response_model=WebhookResponse,
             dependencies=[Depends(_verify_secret)])
def receive_accounting_webhook(
    payload: WebhookPayload,
    db: Session = Depends(get_db),
):
    """
    Receive a webhook event from the external accounting system.

    Supported events:
      - customer.created / customer.updated
      - invoice.created / invoice.updated
      - payment.received / payment.updated

    On receiving an event, the service immediately re-syncs the affected
    entity type from the external API so the local DB stays current.
    """
    logger.info("Webhook received: %s for %s %s",
                payload.event, payload.entity_type, payload.entity_id)

    if payload.entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown entity_type: {payload.entity_type}. "
                   f"Expected one of: {', '.join(sorted(VALID_ENTITY_TYPES))}",
        )

    service = SyncService(db)
    result = service.sync_entity(
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        trigger=f"webhook:{payload.event}",
    )

    message = (
        f"Synced {payload.entity_type} "
        f"(customers={result.customers_synced}, "
        f"invoices={result.invoices_synced}, "
        f"payments={result.payments_synced})"
    )
    if result.errors:
        message += f" with errors: {result.errors}"

    return WebhookResponse(
        received=True,
        event=payload.event,
        message=message,
    )
