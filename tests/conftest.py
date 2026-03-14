"""Shared fixtures for tests."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from datetime import datetime, timedelta, timezone

from app.database import Base, get_db
from app.main import app
from app.models import Customer, Invoice, Payment
from app.models.invoice import InvoiceStatus

TEST_DB_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db):
    def _override():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def seed_data(db):
    """Insert a small set of test data."""
    now = datetime.now(timezone.utc)

    c1 = Customer(id="C1", name="Test Corp", email="test@test.com",
                  credit_limit=100000.0)
    c2 = Customer(id="C2", name="Late Payer Ltd", email="late@test.com",
                  credit_limit=50000.0)
    db.add_all([c1, c2])
    db.flush()

    inv1 = Invoice(id="I1", customer_id="C1", amount=10000.0,
                   due_date=now + timedelta(days=30),
                   issued_date=now - timedelta(days=5),
                   status=InvoiceStatus.PENDING)
    inv2 = Invoice(id="I2", customer_id="C1", amount=20000.0,
                   due_date=now - timedelta(days=10),
                   issued_date=now - timedelta(days=40),
                   status=InvoiceStatus.OVERDUE)
    inv3 = Invoice(id="I3", customer_id="C2", amount=30000.0,
                   due_date=now - timedelta(days=45),
                   issued_date=now - timedelta(days=75),
                   status=InvoiceStatus.OVERDUE)
    db.add_all([inv1, inv2, inv3])
    db.flush()

    pay1 = Payment(id="P1", invoice_id="I2", amount=5000.0,
                   payment_date=now - timedelta(days=5), method="bank_transfer")
    pay2 = Payment(id="P2", invoice_id="I3", amount=10000.0,
                   payment_date=now - timedelta(days=20), method="mpesa")
    db.add_all([pay1, pay2])
    db.commit()
