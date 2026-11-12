import json
import redis.asyncio as redis
from typing import Dict, Any, Optional
import os

# Initialize Redis client (typically configured centrally).
redis_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))


def _cache_key(tenant_id: str, property_id: str, month: Optional[int], year: Optional[int]) -> str:
    # Property IDs are only unique per tenant (prop-001 exists for both tenants),
    # so the tenant MUST be part of the key to avoid cross-tenant leakage.
    period = f"{year}-{month:02d}" if month and year else "all"
    return f"revenue:{tenant_id}:{property_id}:{period}"


async def get_revenue_summary(
    property_id: str,
    tenant_id: str,
    month: Optional[int] = None,
    year: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Fetches revenue summary, utilizing caching to improve performance.
    """
    cache_key = _cache_key(tenant_id, property_id, month, year)

    # Try to get from cache
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    # Revenue calculation is delegated to the reservation service.
    from app.services.reservations import calculate_total_revenue

    result = await calculate_total_revenue(property_id, tenant_id, month, year)

    # Cache the result for 5 minutes
    await redis_client.setex(cache_key, 300, json.dumps(result))

    return result