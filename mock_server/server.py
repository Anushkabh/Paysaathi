"""
Mock External Accounting API
-----------------------------
Simulates a third-party accounting system that exposes customers, invoices,
and payments over REST. Run this on port 8001 before starting the main app.

Usage:  uvicorn mock_server.server:app --port 8001
"""
from fastapi import FastAPI, Query
from datetime import datetime, timedelta
import random

app = FastAPI(title="Mock Accounting System")

# ── Seed data ──

CUSTOMERS = [
    {"id": "CUST-001", "name": "Acme Corp", "email": "billing@acme.com",
     "phone": "+254712345678", "credit_limit": 500000.0},
    {"id": "CUST-002", "name": "Globex Inc", "email": "finance@globex.io",
     "phone": "+254723456789", "credit_limit": 300000.0},
    {"id": "CUST-003", "name": "Nairobi Traders", "email": "info@nairobitraders.co.ke",
     "phone": "+254734567890", "credit_limit": 150000.0},
    {"id": "CUST-004", "name": "Savanna Logistics", "email": "accounts@savanna.co.ke",
     "phone": "+254745678901", "credit_limit": 750000.0},
    {"id": "CUST-005", "name": "Kilimanjaro Supplies", "email": "pay@kili.co.tz",
     "phone": "+255756789012", "credit_limit": 200000.0},
]

_base = datetime(2025, 1, 15)

INVOICES = [
    # Acme – one paid, one overdue, one pending
    {"id": "INV-001", "customer_id": "CUST-001", "amount": 120000.0,
     "due_date": (_base + timedelta(days=30)).isoformat(),
     "issued_date": _base.isoformat(), "status": "paid"},
    {"id": "INV-002", "customer_id": "CUST-001", "amount": 85000.0,
     "due_date": (_base + timedelta(days=45)).isoformat(),
     "issued_date": (_base + timedelta(days=15)).isoformat(), "status": "overdue"},
    {"id": "INV-003", "customer_id": "CUST-001", "amount": 45000.0,
     "due_date": (_base + timedelta(days=120)).isoformat(),
     "issued_date": (_base + timedelta(days=60)).isoformat(), "status": "pending"},

    # Globex – partially paid
    {"id": "INV-004", "customer_id": "CUST-002", "amount": 200000.0,
     "due_date": (_base + timedelta(days=60)).isoformat(),
     "issued_date": _base.isoformat(), "status": "partially_paid"},
    {"id": "INV-005", "customer_id": "CUST-002", "amount": 50000.0,
     "due_date": (_base + timedelta(days=90)).isoformat(),
     "issued_date": (_base + timedelta(days=30)).isoformat(), "status": "pending"},

    # Nairobi Traders – all overdue
    {"id": "INV-006", "customer_id": "CUST-003", "amount": 75000.0,
     "due_date": (_base + timedelta(days=20)).isoformat(),
     "issued_date": _base.isoformat(), "status": "overdue"},
    {"id": "INV-007", "customer_id": "CUST-003", "amount": 30000.0,
     "due_date": (_base + timedelta(days=35)).isoformat(),
     "issued_date": (_base + timedelta(days=5)).isoformat(), "status": "overdue"},

    # Savanna – good standing
    {"id": "INV-008", "customer_id": "CUST-004", "amount": 300000.0,
     "due_date": (_base + timedelta(days=30)).isoformat(),
     "issued_date": _base.isoformat(), "status": "paid"},
    {"id": "INV-009", "customer_id": "CUST-004", "amount": 150000.0,
     "due_date": (_base + timedelta(days=90)).isoformat(),
     "issued_date": (_base + timedelta(days=30)).isoformat(), "status": "pending"},

    # Kilimanjaro – overdue
    {"id": "INV-010", "customer_id": "CUST-005", "amount": 95000.0,
     "due_date": (_base + timedelta(days=25)).isoformat(),
     "issued_date": _base.isoformat(), "status": "overdue"},
]

PAYMENTS = [
    # Full payment for INV-001
    {"id": "PAY-001", "invoice_id": "INV-001", "amount": 120000.0,
     "payment_date": (_base + timedelta(days=28)).isoformat(),
     "method": "bank_transfer", "reference": "TXN-9001"},

    # Partial payment for INV-004
    {"id": "PAY-002", "invoice_id": "INV-004", "amount": 80000.0,
     "payment_date": (_base + timedelta(days=40)).isoformat(),
     "method": "mpesa", "reference": "MPESA-4420"},
    {"id": "PAY-003", "invoice_id": "INV-004", "amount": 50000.0,
     "payment_date": (_base + timedelta(days=55)).isoformat(),
     "method": "bank_transfer", "reference": "TXN-9002"},

    # Full payment for INV-008
    {"id": "PAY-004", "invoice_id": "INV-008", "amount": 300000.0,
     "payment_date": (_base + timedelta(days=25)).isoformat(),
     "method": "bank_transfer", "reference": "TXN-9003"},

    # Small payment against overdue INV-006
    {"id": "PAY-005", "invoice_id": "INV-006", "amount": 10000.0,
     "payment_date": (_base + timedelta(days=50)).isoformat(),
     "method": "mpesa", "reference": "MPESA-4421"},

    # Partial for INV-002 (overdue)
    {"id": "PAY-006", "invoice_id": "INV-002", "amount": 25000.0,
     "payment_date": (_base + timedelta(days=60)).isoformat(),
     "method": "cheque", "reference": "CHQ-1122"},
]


# ── Endpoints ──

@app.get("/api/customers")
def list_customers():
    return {"data": CUSTOMERS, "total": len(CUSTOMERS)}


@app.get("/api/customers/{customer_id}")
def get_customer(customer_id: str):
    for c in CUSTOMERS:
        if c["id"] == customer_id:
            return c
    return {"error": "Customer not found"}, 404


@app.get("/api/invoices")
def list_invoices(customer_id: str = Query(default=None)):
    results = INVOICES
    if customer_id:
        results = [i for i in INVOICES if i["customer_id"] == customer_id]
    return {"data": results, "total": len(results)}


@app.get("/api/invoices/{invoice_id}")
def get_invoice(invoice_id: str):
    for i in INVOICES:
        if i["id"] == invoice_id:
            return i
    return {"error": "Invoice not found"}, 404


@app.get("/api/payments")
def list_payments(invoice_id: str = Query(default=None)):
    results = PAYMENTS
    if invoice_id:
        results = [p for p in PAYMENTS if p["invoice_id"] == invoice_id]
    return {"data": results, "total": len(results)}


@app.get("/api/payments/{payment_id}")
def get_payment(payment_id: str):
    for p in PAYMENTS:
        if p["id"] == payment_id:
            return p
    return {"error": "Payment not found"}, 404
