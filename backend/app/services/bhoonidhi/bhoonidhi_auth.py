"""Backward-compatible accessors for the central Bhoonidhi client."""

from typing import Optional

from app.services.bhoonidhi.bhoonidhi_client import BhoonidhiAuthError, get_bhoonidhi_client


async def get_bhoonidhi_token() -> Optional[str]:
    try:
        client = await get_bhoonidhi_client()
        token = await client._authenticate()
        return token.access_token
    except BhoonidhiAuthError:
        return None


def clear_bhoonidhi_token() -> None:
    # Kept for existing imports; request code uses the central client's lifecycle.
    from app.services.bhoonidhi.bhoonidhi_client import _default_client
    _default_client.clear_token()
