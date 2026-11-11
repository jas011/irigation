import logging
from app.services.gee.gee_service import initialize_gee, get_gee_status
from app.services.bhoonidhi.bhoonidhi_client import BhoonidhiError, TARGET_COLLECTION, get_bhoonidhi_client

logger = logging.getLogger("agrisense.external")


async def check_bhoonidhi_status() -> dict:
    status = {
        "authentication": False,
        "token": "NONE",
        "token_type": None,
        "collections_ok": False,
        "collections_count": 0,
        "target_collection_found": False,
        "error": None,
    }

    client = await get_bhoonidhi_client()
    status["user_id"] = client.user_id
    status["credentials_configured"] = client.credentials_configured
    if not client.credentials_configured:
        status["error"] = "Credentials missing"
        return status
    try:
        token = await client._authenticate()
        status["authentication"] = True
        status["access_token"] = bool(token.access_token)
        status["token"] = "PRESENT"
        status["token_type"] = token.token_type
        data = await client.get_collections()
        collections = data.get("collections", data.get("data", data if isinstance(data, list) else []))
        status["collections_ok"] = True
        status["collections_count"] = len(collections) if isinstance(collections, list) else 0
        status["target_collection_found"] = any(
            (c.get("name") == TARGET_COLLECTION or c.get("id") == TARGET_COLLECTION) if isinstance(c, dict) else c == TARGET_COLLECTION
            for c in collections
        ) if isinstance(collections, list) else False
    except BhoonidhiError as exc:
        status["error"] = str(exc)

    return status


def format_startup_report(gee_status: dict, bhoonidhi_status: dict) -> str:
    lines = []
    lines.append("============================================================")
    lines.append("GOOGLE EARTH ENGINE")
    lines.append("============================================================")
    lines.append(f"Project ID: {gee_status.get('project_id')}")
    auth = "detected" if gee_status.get("authenticated") else "missing"
    init = "successful" if gee_status.get("initialized") else "failed"
    conn = "successful" if not gee_status.get("error") else f"failed: {gee_status.get('error')}"
    state = "READY" if gee_status.get("initialized") and gee_status.get("authenticated") and not gee_status.get("error") else "NOT READY"
    lines.append(f"Authentication: {auth}")
    lines.append(f"Initialization: {init}")
    lines.append(f"Connectivity: {conn}")
    lines.append(f"Status: {state}")
    lines.append("============================================================")

    lines.append("BHOONIDHI")
    lines.append("============================================================")
    lines.append(f"User ID: {bhoonidhi_status.get('user_id')}")
    lines.append(f"Authentication: {'SUCCESS' if bhoonidhi_status.get('authentication') else 'FAIL'}")
    lines.append(f"Token: {bhoonidhi_status.get('token')}")
    lines.append(f"Token Type: {bhoonidhi_status.get('token_type')}")
    lines.append(f"Collection API: {'SUCCESS' if bhoonidhi_status.get('collections_ok') else 'FAIL'}")
    lines.append(f"Collections Available: {bhoonidhi_status.get('collections_count')}")
    lines.append(f"Target Collection:\nSentinel-1A_SAR-IW_GRD")
    lines.append(f"Target Collection: {'FOUND' if bhoonidhi_status.get('target_collection_found') else 'NOT FOUND'}")
    lines.append(f"Status: {'READY' if bhoonidhi_status.get('authentication') and bhoonidhi_status.get('collections_ok') and bhoonidhi_status.get('target_collection_found') else 'NOT READY'}")
    lines.append("============================================================")
    return "\n".join(lines)


async def run_startup_checks() -> dict:
    # Run GEE init (sync) and Bhoonidhi (async) checks
    gee_ok = initialize_gee()
    gee_status = get_gee_status()
    bhoonidhi_status = await check_bhoonidhi_status()
    report = format_startup_report(gee_status, bhoonidhi_status)
    logger.info("\n%s", report)
    return {"gee": gee_status, "bhoonidhi": bhoonidhi_status, "report": report}
