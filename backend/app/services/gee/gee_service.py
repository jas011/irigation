import os
import time
import logging
import threading
from typing import Any

from dotenv import load_dotenv
import ee

load_dotenv()

logger = logging.getLogger("agrisense.gee")

_GEE_GETINFO_LOCK = threading.Lock()


def log_terminal(tag: str, message: str) -> None:
    """Print formatted log message to terminal stdout and logger."""
    formatted = f"[{tag}] {message}"
    print(formatted, flush=True)
    logger.info(message)



def _is_retryable_gee_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(
        marker in message
        for marker in (
            "too many concurrent aggregations",
            "429",
            "rate limit",
            "resourceexhausted",
            "temporarily unavailable",
            "timed out",
            "timeout",
        )
    )


def gee_get_info(obj: Any, *, max_retries: int = 5, base_delay: float = 2.0) -> Any:
    """Run a GEE server-side fetch with retry and serialization to avoid 429 bursts."""
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            with _GEE_GETINFO_LOCK:
                return obj.getInfo()
        except Exception as exc:  # noqa: BLE001 - Earth Engine raises many concrete exceptions here.
            last_error = exc
            if not _is_retryable_gee_error(exc) or attempt == max_retries:
                raise
            delay = base_delay * (2 ** attempt)
            logger.warning(
                "Earth Engine request rate-limited; retrying in %.1fs (attempt %s/%s): %s",
                delay,
                attempt + 1,
                max_retries + 1,
                exc,
            )
            time.sleep(delay)
    if last_error is not None:
        raise last_error
    raise RuntimeError("Earth Engine request failed without exception details")


# Internal status tracking
_status = {
    "initialized": False,
    "authenticated": False,
    "project_id": None,
    "error": None,
    "last_checked": None,
}


def _require_project_env():
    project = os.getenv("GEE_PROJECT_ID")
    if not project:
        raise EnvironmentError("GEE_PROJECT_ID missing in environment. Please set it in backend/.env")
    return project


def initialize_gee() -> bool:
    """Initialize Google Earth Engine using `GEE_PROJECT_ID` from .env and verify connectivity.

    Returns True on success, False on failure. Updates `get_gee_status()` state.
    """
    global _status
    if _status["initialized"]:
        return True

    try:
        project = _require_project_env()
        _status["project_id"] = project
    except EnvironmentError as e:
        _status.update({"error": str(e), "initialized": False, "authenticated": False})
        logger.error("GEE configuration error: %s", str(e))
        return False

    try:
        logger.info("Initializing Earth Engine with project: %s", project)
        ee.Initialize(project=project)
        # Verify server communication with a lightweight request.
        # This is wrapped to serialize and retry against GEE's transient 429s.
        _ = gee_get_info(ee.Number(1))
        _status.update({
            "initialized": True,
            "authenticated": True,
            "error": None,
            "last_checked": int(time.time())
        })
        logger.info("Earth Engine initialization and connectivity verified.")
        return True
    except Exception as e:
        _status.update({"initialized": False, "authenticated": False, "error": str(e), "last_checked": int(time.time())})
        logger.error("Earth Engine initialization/connectivity failed: %s", str(e))
        return False


def get_gee_status() -> dict:
    """Return a sanitized status dict for Earth Engine.

    Does not expose credentials or tokens.
    """
    global _status
    # Always include configured project id if available
    status = {
        "initialized": bool(_status.get("initialized")),
        "authenticated": bool(_status.get("authenticated")),
        "project_id": _status.get("project_id"),
        "error": _status.get("error")
    }
    return status


def is_gee_ready() -> bool:
    if not _status.get("initialized"):
        return initialize_gee()
    return True
