from datetime import date

from fastapi import APIRouter, Query

from app.deps import DbDep, OperatorUser
from app.schemas import AnalyticsOut
from app.services.analytics import analytics as run_analytics

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("", response_model=AnalyticsOut)
def analytics(
    _: OperatorUser,
    db: DbDep,
    start: date = Query(..., description="Inclusive start date (YYYY-MM-DD)"),
    end: date = Query(..., description="Inclusive end date (YYYY-MM-DD)"),
) -> AnalyticsOut:
    return AnalyticsOut(**run_analytics(db, start, end))
