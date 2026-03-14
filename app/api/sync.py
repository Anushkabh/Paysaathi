from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.sync_service import SyncService
from app.schemas.schemas import SyncResult

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/", response_model=SyncResult)
def trigger_sync(db: Session = Depends(get_db)):
    """Manually trigger a full sync from the external accounting system."""
    service = SyncService(db)
    return service.sync_all()
