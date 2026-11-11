import logging
import os
from typing import Any, Dict, List

from app.services.bhoonidhi.bhoonidhi_client import BhoonidhiAuthError, BhoonidhiClient, BhoonidhiError

logger = logging.getLogger("agrisense.analysis.bhoonidhi")


class BhoonidhiService:
    @staticmethod
    def configured() -> bool:
        return bool(os.getenv("BHOONIDHI_USER_ID") and os.getenv("BHOONIDHI_PASSWORD"))

    @classmethod
    async def validate_aoi(cls, geometry: Dict[str, Any], start_date: str, end_date: str) -> List[Dict[str, Any]]:
        if not cls.configured():
            raise BhoonidhiAuthError("Bhoonidhi credentials are not configured in backend/.env.")

        client = BhoonidhiClient(
            user_id=os.getenv("BHOONIDHI_USER_ID"),
            password=os.getenv("BHOONIDHI_PASSWORD"),
        )
        try:
            products = await client.search_sentinel1(geometry, start_date, end_date)
        except BhoonidhiError:
            logger.exception("Bhoonidhi request failed for AOI validation.")
            raise
        return products or []
