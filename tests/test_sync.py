"""Tests for the sync service using a fake client."""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.services.sync_service import SyncService
from app.schemas.schemas import ExternalCustomer, ExternalInvoice, ExternalPayment
from app.models import Customer, Invoice, Payment


def _make_fake_client():
    client = MagicMock()
    client.fetch_customers.return_value = [
        ExternalCustomer(id="C1", name="Alpha", email="a@b.com", credit_limit=1000),
    ]
    client.fetch_invoices.return_value = [
        ExternalInvoice(
            id="I1", customer_id="C1", amount=500,
            due_date=datetime(2025, 6, 1, tzinfo=timezone.utc),
            issued_date=datetime(2025, 5, 1, tzinfo=timezone.utc),
            status="pending",
        ),
    ]
    client.fetch_payments.return_value = [
        ExternalPayment(
            id="P1", invoice_id="I1", amount=200,
            payment_date=datetime(2025, 5, 15, tzinfo=timezone.utc),
            method="mpesa",
        ),
    ]
    return client


class TestSyncService:
    def test_full_sync(self, db):
        client = _make_fake_client()
        result = SyncService(db, client=client).sync_all()

        assert result.customers_synced == 1
        assert result.invoices_synced == 1
        assert result.payments_synced == 1
        assert result.errors == []

        assert db.get(Customer, "C1") is not None
        assert db.get(Invoice, "I1") is not None
        assert db.get(Payment, "P1") is not None

    def test_idempotent_sync(self, db):
        """Running sync twice should upsert, not duplicate."""
        client = _make_fake_client()
        SyncService(db, client=client).sync_all()
        SyncService(db, client=client).sync_all()

        assert db.query(Customer).count() == 1
        assert db.query(Invoice).count() == 1
        assert db.query(Payment).count() == 1

    def test_sync_handles_api_error(self, db):
        from app.external.accounting_client import AccountingAPIError

        client = MagicMock()
        client.fetch_customers.side_effect = AccountingAPIError("down")
        client.fetch_invoices.return_value = []
        client.fetch_payments.return_value = []

        result = SyncService(db, client=client).sync_all()

        assert result.customers_synced == 0
        assert len(result.errors) == 1
        assert "down" in result.errors[0]
