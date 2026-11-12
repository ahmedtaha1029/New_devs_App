import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Optional

from sqlalchemy import text

logger = logging.getLogger(__name__)

CENT = Decimal("0.01")


def _money(value) -> str:
    """Round once, at the very end, to cents (half-up) and return as a string."""
    return str(Decimal(str(value or 0)).quantize(CENT, rounding=ROUND_HALF_UP))


async def calculate_total_revenue(
    property_id: str,
    tenant_id: str,
    month: Optional[int] = None,
    year: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Aggregates revenue from the database for one tenant's property.

    If month/year are given, reservations are bucketed by check-in date in the
    PROPERTY's local timezone (not UTC), so a booking at 23:30 UTC on Feb 29
    for a Paris property correctly counts toward March.
    """
    from app.core.database_pool import db_pool

    if not db_pool.session_factory:
        await db_pool.initialize()
    if not db_pool.session_factory:
        raise RuntimeError("Database pool not available")

    params: Dict[str, Any] = {"property_id": property_id, "tenant_id": tenant_id}
    period_filter = ""
    if month and year:
        # Local-time month boundaries, evaluated in the property's timezone.
        period_filter = """
            AND (r.check_in_date AT TIME ZONE p.timezone) >= make_timestamp(:year, :month, 1, 0, 0, 0)
            AND (r.check_in_date AT TIME ZONE p.timezone) <
                make_timestamp(:year, :month, 1, 0, 0, 0) + interval '1 month'
        """
        params.update({"month": month, "year": year})

    query = text(f"""
        SELECT
            COALESCE(SUM(r.total_amount), 0) AS total_revenue,
            COUNT(r.id) AS reservation_count
        FROM properties p
        LEFT JOIN reservations r
               ON r.property_id = p.id
              AND r.tenant_id = p.tenant_id
        WHERE p.id = :property_id
          AND p.tenant_id = :tenant_id
          {period_filter}
    """)

    async with db_pool.get_session() as session:
        row = (await session.execute(query, params)).fetchone()

    return {
        "property_id": property_id,
        "tenant_id": tenant_id,
        "total": _money(row.total_revenue if row else 0),
        "currency": "USD",
        "count": int(row.reservation_count) if row else 0,
    }