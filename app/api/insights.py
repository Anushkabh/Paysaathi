from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.insights_service import InsightsService
from app.schemas.schemas import (
    CustomerBalance, OverdueInvoice, AgingBucket, CustomerCreditReport,
)

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/balances", response_model=list[CustomerBalance])
def outstanding_balances(db: Session = Depends(get_db)):
    """Outstanding balance summary for every customer."""
    return InsightsService(db).get_customer_balances()


@router.get("/overdue", response_model=list[OverdueInvoice])
def overdue_invoices(db: Session = Depends(get_db)):
    """All overdue invoices sorted by days overdue (descending)."""
    return InsightsService(db).get_overdue_invoices()


@router.get("/aging", response_model=list[AgingBucket])
def aging_report(db: Session = Depends(get_db)):
    """Accounts-receivable aging report (0-30, 31-60, 61-90, 90+ days)."""
    return InsightsService(db).get_aging_report()


@router.get("/credit-report/{customer_id}", response_model=CustomerCreditReport)
def customer_credit_report(customer_id: str, db: Session = Depends(get_db)):
    """Full credit/risk report for a single customer."""
    report = InsightsService(db).get_customer_credit_report(customer_id)
    if not report:
        raise HTTPException(status_code=404, detail="Customer not found")
    return report
