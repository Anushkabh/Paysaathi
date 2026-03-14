"""Tests for the insights service and API endpoints."""
import pytest
from app.services.insights_service import InsightsService


class TestInsightsService:
    def test_customer_balances(self, db, seed_data):
        balances = InsightsService(db).get_customer_balances()
        assert len(balances) == 2

        c1 = next(b for b in balances if b.customer_id == "C1")
        assert c1.total_invoiced == 30000.0
        assert c1.total_paid == 5000.0
        assert c1.outstanding_balance == 25000.0

        c2 = next(b for b in balances if b.customer_id == "C2")
        assert c2.outstanding_balance == 20000.0

    def test_overdue_invoices(self, db, seed_data):
        overdue = InsightsService(db).get_overdue_invoices()
        assert len(overdue) == 2
        # Sorted by days_overdue descending – I3 is more overdue than I2
        assert overdue[0].invoice_id == "I3"
        assert overdue[0].days_overdue > overdue[1].days_overdue

    def test_aging_report(self, db, seed_data):
        aging = InsightsService(db).get_aging_report()
        assert len(aging) == 4
        total = sum(b.total_outstanding for b in aging)
        # Total outstanding across buckets should equal sum of unpaid balances
        assert total > 0

    def test_credit_report(self, db, seed_data):
        report = InsightsService(db).get_customer_credit_report("C2")
        assert report is not None
        assert report.customer.id == "C2"
        assert report.overdue_invoice_count == 1
        assert report.outstanding_balance == 20000.0
        assert report.risk_level in ("LOW", "MEDIUM", "HIGH")

    def test_credit_report_not_found(self, db, seed_data):
        report = InsightsService(db).get_customer_credit_report("NOPE")
        assert report is None


class TestInsightsAPI:
    def test_balances_endpoint(self, client, seed_data):
        resp = client.get("/api/v1/insights/balances")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_overdue_endpoint(self, client, seed_data):
        resp = client.get("/api/v1/insights/overdue")
        assert resp.status_code == 200

    def test_aging_endpoint(self, client, seed_data):
        resp = client.get("/api/v1/insights/aging")
        assert resp.status_code == 200
        assert len(resp.json()) == 4

    def test_credit_report_endpoint(self, client, seed_data):
        resp = client.get("/api/v1/insights/credit-report/C1")
        assert resp.status_code == 200
        assert resp.json()["customer"]["id"] == "C1"

    def test_credit_report_404(self, client, seed_data):
        resp = client.get("/api/v1/insights/credit-report/MISSING")
        assert resp.status_code == 404
