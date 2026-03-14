from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Invoice
from app.schemas.schemas import InvoiceOut

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.get("/", response_model=list[InvoiceOut])
def list_invoices(
    customer_id: str = Query(default=None),
    status: str = Query(default=None),
    db: Session = Depends(get_db),
):
    q = db.query(Invoice)
    if customer_id:
        q = q.filter(Invoice.customer_id == customer_id)
    if status:
        q = q.filter(Invoice.status == status)
    return q.all()
