from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.sync_service import SyncService, SyncStrategy
from app.schemas.schemas import SyncResult

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/", response_model=SyncResult)
def trigger_sync(
    strategy: SyncStrategy = Query(
        default=SyncStrategy.FULL,
        description="full = pull everything, incremental = only changes since last sync",
    ),
    db: Session = Depends(get_db),
):
    """Manually trigger a sync from the external accounting system."""
    service = SyncService(db)
    return service.sync_all(trigger="manual", strategy=strategy)
