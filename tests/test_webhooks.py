"""Tests for the webhook receiver."""
import pytest
from datetime import datetime, timezone

from app.config import settings


WEBHOOK_URL = "/api/v1/webhooks/accounting"
VALID_HEADERS = {"X-Webhook-Secret": settings.WEBHOOK_SECRET}


class TestWebhookReceiver:
    def _payload(self, event="invoice.updated", entity_type="invoice",
                 entity_id="INV-001"):
        return {
            "event": event,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def test_rejects_missing_secret(self, client, seed_data):
        resp = client.post(WEBHOOK_URL, json=self._payload())
        assert resp.status_code == 422  # missing header

    def test_rejects_invalid_secret(self, client, seed_data):
        resp = client.post(
            WEBHOOK_URL, json=self._payload(),
            headers={"X-Webhook-Secret": "wrong"},
        )
        assert resp.status_code == 401

    def test_accepts_valid_webhook(self, client, seed_data):
        resp = client.post(
            WEBHOOK_URL, json=self._payload(),
            headers=VALID_HEADERS,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["received"] is True
        assert body["event"] == "invoice.updated"

    def test_rejects_unknown_entity_type(self, client, seed_data):
        resp = client.post(
            WEBHOOK_URL,
            json=self._payload(entity_type="unknown"),
            headers=VALID_HEADERS,
        )
        assert resp.status_code == 422

    def test_customer_webhook(self, client, seed_data):
        resp = client.post(
            WEBHOOK_URL,
            json=self._payload(event="customer.created", entity_type="customer",
                               entity_id="C1"),
            headers=VALID_HEADERS,
        )
        assert resp.status_code == 200

    def test_payment_webhook(self, client, seed_data):
        resp = client.post(
            WEBHOOK_URL,
            json=self._payload(event="payment.received", entity_type="payment",
                               entity_id="P1"),
            headers=VALID_HEADERS,
        )
        assert resp.status_code == 200
