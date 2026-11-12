from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any, Optional
from app.services.cache import get_revenue_summary
from app.core.auth import authenticate_request as get_current_user

router = APIRouter()


@router.get("/dashboard/summary")
async def get_dashboard_summary(
    property_id: str,
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2000, le=2100),
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:

    # Never fall back to a shared/default tenant: that is how data leaks between clients.
    tenant_id = getattr(current_user, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="No tenant associated with this user")

    if (month is None) != (year is None):
        raise HTTPException(status_code=422, detail="month and year must be provided together")

    revenue_data = await get_revenue_summary(property_id, tenant_id, month, year)

    return {
        "property_id": revenue_data['property_id'],
        # Exact decimal string rounded to cents; avoids float drift.
        "total_revenue": revenue_data['total'],
        "currency": revenue_data['currency'],
        "reservations_count": revenue_data['count']
    }