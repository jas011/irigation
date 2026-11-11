import logging
import os

import ee
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("agrisense.gee.health")


class GEEHealthError(RuntimeError):
    pass


def verify_gee_authentication() -> dict:
    project_id = os.getenv("GEE_PROJECT_ID")
    if not project_id:
        raise GEEHealthError("GEE_PROJECT_ID is missing from the backend environment. Configure backend/.env before analysis.")

    try:
        ee.Initialize(project=project_id)
        value = ee.Number(1).getInfo()
    except Exception as exc:  # noqa: BLE001
        logger.exception("GEE authentication failed for project %s", project_id)
        raise GEEHealthError(f"GEE authentication failed: {exc}") from exc

    if value != 1:
        raise GEEHealthError("GEE test request returned an unexpected result.")

    return {
        "status": "ready",
        "project_id": project_id,
        "authentication_check": "passed",
    }
