"""Application-facing Bhoonidhi operations."""

from typing import Any, Dict, List

from app.services.bhoonidhi.bhoonidhi_client import TARGET_COLLECTION, get_bhoonidhi_client


async def search_bhoonidhi_sentinel1(
    geometry_geojson: Dict[str, Any],
    start_date: str,
    end_date: str,
) -> List[Dict[str, Any]]:
    client = await get_bhoonidhi_client()
    return await client.search_sentinel1(geometry_geojson, start_date, end_date, collection=TARGET_COLLECTION)
