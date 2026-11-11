"""Async client for the current Bhoonidhi API.

The client owns credentials, token lifecycle, retries and response validation so
application services never need to handle authentication themselves.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Dict, List, Optional
from urllib.parse import urljoin

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("agrisense.bhoonidhi")

BASE_URL = "https://bhoonidhi-api.nrsc.gov.in"
TARGET_COLLECTION = "Sentinel-1A_SAR-IW_GRD"
RETRYABLE_STATUS = {429, 500, 503, 504}


class BhoonidhiError(RuntimeError):
    def __init__(self, message: str, status_code: Optional[int] = None, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class BhoonidhiAuthError(BhoonidhiError):
    pass


@dataclass
class TokenState:
    access_token: str
    refresh_token: Optional[str]
    token_type: str
    expires_at: float
    user_id: str

    def usable(self, margin: int) -> bool:
        return time.time() < self.expires_at - margin


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return {"raw": response.text[:500]}


def _error_message(status: int, payload: Any) -> str:
    if isinstance(payload, dict):
        detail = payload.get("Description") or payload.get("description") or payload.get("message")
        code = payload.get("ErrorCode") or payload.get("errorCode") or payload.get("code")
        if code or detail:
            return f"Bhoonidhi API error {code or status}: {detail or 'request failed'}"
    messages = {400: "bad request", 403: "access forbidden", 404: "resource not found", 406: "request not acceptable"}
    return f"Bhoonidhi API error {status}: {messages.get(status, 'request failed')}"


def _is_no_results_response(status: int, payload: Any) -> bool:
    """Bhoonidhi uses HTTP 404 for an otherwise valid empty catalogue search."""
    if status != 404:
        return False
    if isinstance(payload, dict):
        text = " ".join(str(value) for value in payload.values())
    else:
        text = str(payload)
    return "NO RESULTS FOUND" in text.upper()


class BhoonidhiClient:
    def __init__(
        self,
        base_url: str = BASE_URL,
        user_id: Optional[str] = None,
        password: Optional[str] = None,
        timeout: float = 30.0,
        token_margin: int = 45,
        max_retries: int = 3,
        client_factory: Optional[Callable[..., httpx.AsyncClient]] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.user_id = user_id if user_id is not None else os.getenv("BHOONIDHI_USER_ID")
        self.password = password if password is not None else os.getenv("BHOONIDHI_PASSWORD")
        self.timeout = timeout
        self.token_margin = token_margin
        self.max_retries = max_retries
        self._token: Optional[TokenState] = None
        self._auth_lock = asyncio.Lock()
        self._request_lock = asyncio.Lock()
        self._last_request = 0.0
        self.client_factory = client_factory or httpx.AsyncClient

    @property
    def credentials_configured(self) -> bool:
        return bool(self.user_id and self.password)

    def clear_token(self) -> None:
        self._token = None

    async def _authenticate(self, refresh: bool = True) -> TokenState:
        async with self._auth_lock:
            if self._token and self._token.usable(self.token_margin):
                return self._token
            if refresh and self._token and self._token.refresh_token:
                try:
                    return await self._token_request({
                        "userId": self._token.user_id,
                        "refresh_token": self._token.refresh_token,
                        "grant_type": "refresh_token",
                    }, "refresh")
                except BhoonidhiError as exc:
                    logger.warning("Bhoonidhi token refresh failed (%s); using password authentication", exc)
            if not self.credentials_configured:
                raise BhoonidhiAuthError("Bhoonidhi credentials are not configured")
            return await self._token_request({
                "userId": self.user_id,
                "password": self.password,
                "grant_type": "password",
            }, "password")

    async def _token_request(self, payload: Dict[str, str], mode: str) -> TokenState:
        logger.info("Bhoonidhi %s authentication attempt", mode)
        async with self.client_factory(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/auth/token", json=payload)
        data = _safe_json(response)
        if response.status_code != 200 or not isinstance(data, dict) or not data.get("access_token"):
            raise BhoonidhiAuthError(_error_message(response.status_code, data), response.status_code, data)
        expires = int(data.get("expires_in", 1200))
        self._token = TokenState(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            token_type=data.get("token_type") or "Bearer",
            expires_at=time.time() + expires,
            user_id=data.get("userId") or payload.get("userId") or self.user_id or "",
        )
        logger.info("Bhoonidhi authentication succeeded; token cached for %ss", expires)
        return self._token

    async def _throttle(self) -> None:
        async with self._request_lock:
            wait = 1 / 3 - (time.monotonic() - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()

    async def _request(self, method: str, path_or_url: str, *, auth: bool = True, retry_auth: bool = True, **kwargs: Any) -> httpx.Response:
        url = path_or_url if path_or_url.startswith("http") else urljoin(f"{self.base_url}/", path_or_url.lstrip("/"))
        for attempt in range(self.max_retries + 1):
            token = await self._authenticate() if auth else None
            headers = {"Accept": "application/json", "Content-Type": "application/json", **kwargs.pop("headers", {})}
            if token:
                headers["Authorization"] = f"{token.token_type} {token.access_token}"
            await self._throttle()
            async with self.client_factory(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.request(method, url, headers=headers, **kwargs)
            if response.status_code == 401 and auth and retry_auth:
                # Keep the refresh token while invalidating only the access
                # token, so the next authentication attempt can refresh first.
                if self._token:
                    self._token = TokenState(
                        access_token="",
                        refresh_token=self._token.refresh_token,
                        token_type=self._token.token_type,
                        expires_at=0,
                        user_id=self._token.user_id,
                    )
                return await self._request(method, url, auth=True, retry_auth=False, **kwargs)
            if response.status_code in RETRYABLE_STATUS and attempt < self.max_retries:
                delay = min(8.0, 0.5 * (2 ** attempt)) + random.uniform(0, 0.25)
                logger.warning("Bhoonidhi %s from %s; retrying in %.2fs", response.status_code, url, delay)
                await asyncio.sleep(delay)
                continue
            return response
        raise BhoonidhiError("Bhoonidhi request retry limit reached")

    @staticmethod
    def _validate_collection_response(data: Any) -> Any:
        if not isinstance(data, (dict, list)):
            raise BhoonidhiError("Malformed Bhoonidhi collections response", payload=data)
        return data

    async def get_collections(self) -> Any:
        response = await self._request("GET", "/data/collections")
        data = _safe_json(response)
        if response.status_code != 200:
            raise BhoonidhiError(_error_message(response.status_code, data), response.status_code, data)
        return self._validate_collection_response(data)

    async def search(self, payload: Dict[str, Any], *, paginate: bool = True) -> Dict[str, Any]:
        response = await self._request("POST", "/data/search", json=payload)
        data = _safe_json(response)
        if _is_no_results_response(response.status_code, data):
            return {"type": "FeatureCollection", "features": [], "context": {"returned": 0}}
        if response.status_code != 200:
            raise BhoonidhiError(_error_message(response.status_code, data), response.status_code, data)
        if not isinstance(data, dict) or data.get("type") != "FeatureCollection" or not isinstance(data.get("features", []), list):
            raise BhoonidhiError("Malformed Bhoonidhi STAC search response", payload=data)
        features = list(data.get("features", []))
        visited = set()
        next_url = next((link.get("href") for link in data.get("links", []) if link.get("rel") == "next"), None)
        while paginate and next_url and next_url not in visited:
            visited.add(next_url)
            page = await self._request("GET", next_url)
            page_data = _safe_json(page)
            if page.status_code != 200:
                raise BhoonidhiError(_error_message(page.status_code, page_data), page.status_code, page_data)
            if not isinstance(page_data, dict) or not isinstance(page_data.get("features", []), list):
                raise BhoonidhiError("Malformed Bhoonidhi pagination response", payload=page_data)
            features.extend(page_data["features"])
            next_url = next((link.get("href") for link in page_data.get("links", []) if link.get("rel") == "next"), None)
        unique: Dict[str, Dict[str, Any]] = {}
        for feature in features:
            if isinstance(feature, dict):
                key = feature.get("id") or f"fallback:{len(unique)}"
                unique.setdefault(key, feature)
        return {**data, "features": list(unique.values()), "context": {**(data.get("context") or {}), "returned": len(unique)}}

    async def search_bbox(self, collections: List[str], bbox: List[float], datetime_range: str, **kwargs: Any) -> Dict[str, Any]:
        """Search using Bhoonidhi's native bbox field."""
        return await self.search({"collections": collections, "bbox": [str(value) for value in bbox], "datetime": datetime_range, **kwargs})

    async def search_intersects(self, collections: List[str], geometry: Dict[str, Any], datetime_range: str, **kwargs: Any) -> Dict[str, Any]:
        """Search using Bhoonidhi's native GeoJSON intersects field."""
        return await self.search({"collections": collections, "intersects": geometry, "datetime": datetime_range, **kwargs})

    async def search_sentinel1(self, geometry: Dict[str, Any], start_date: str, end_date: str, *, collection: str = TARGET_COLLECTION, chunk_days: int = 30) -> List[Dict[str, Any]]:
        bbox = _geometry_bbox(geometry)
        start = _parse_date(start_date)
        end = _parse_date(end_date)
        print(f"[Bhoonidhi NRSC] Querying collection '{collection}' for BBOX {[round(v, 4) for v in bbox]} (Dates: {start_date} to {end_date})...", flush=True)
        products: Dict[str, Dict[str, Any]] = {}
        cursor = start
        while cursor < end:
            chunk_end = min(cursor + timedelta(days=chunk_days), end)
            payload = {"collections": [collection], "bbox": [str(v) for v in bbox], "datetime": f"{_rfc3339(cursor)}/{_rfc3339(chunk_end - timedelta(seconds=1))}", "limit": 100, "filter": {"args": [{"property": "Online"}, "Y"], "op": "eq"}, "filter-lang": "cql2-json"}
            result = await self.search(payload)
            for feature in result["features"]:
                product_id = feature.get("id")
                if product_id:
                    products[product_id] = feature
            cursor = chunk_end
        normalized = [_normalize_product(feature, start_date) for feature in products.values()]
        if normalized:
            sample_ids = ", ".join(p['id'] for p in normalized[:3])
            print(f"[Bhoonidhi NRSC] Found {len(normalized)} online products. Samples: [{sample_ids}{'...' if len(normalized) > 3 else ''}]", flush=True)
        else:
            print(f"[Bhoonidhi NRSC] 0 online products found for this AOI and date range.", flush=True)
        return normalized


    async def download_product(self, product_id: str, collection: str, destination: Path, *, online: Any = "Y") -> Path:
        if str(online).upper() != "Y":
            raise BhoonidhiError("Product is offline and must be ordered through Bhoonidhi Browse & Order", status_code=412)
        destination.parent.mkdir(parents=True, exist_ok=True)
        for auth_attempt in range(2):
            token = await self._authenticate()
            await self._throttle()
            headers = {"Authorization": f"{token.token_type} {token.access_token}", "Accept": "application/octet-stream"}
            async with self.client_factory(timeout=self.timeout, follow_redirects=True) as client:
                async with client.stream("GET", f"{self.base_url}/download", params={"id": product_id, "collection": collection}, headers=headers) as response:
                    if response.status_code == 401 and auth_attempt == 0:
                        if self._token:
                            self._token = TokenState("", self._token.refresh_token, self._token.token_type, 0, self._token.user_id)
                        continue
                    if response.status_code != 200:
                        await response.aread()
                        data = _safe_json(response)
                        raise BhoonidhiError(_error_message(response.status_code, data), response.status_code, data)
                    with destination.open("wb") as output:
                        async for chunk in response.aiter_bytes(1024 * 1024):
                            output.write(chunk)
                    return destination
        raise BhoonidhiAuthError("Bhoonidhi download authentication failed after retry", status_code=401)


def _parse_date(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _rfc3339(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _geometry_bbox(geometry: Dict[str, Any]) -> List[float]:
    """Return a bbox for a GeoJSON geometry, Feature, or FeatureCollection.

    ``shapely.geometry.mapping`` (used for saved field boundaries) returns
    coordinate tuples, while JSON parsed from an HTTP request uses lists. Both
    are valid GeoJSON coordinate containers and must be handled identically.
    """
    points: List[List[float]] = []
    def walk(value: Any) -> None:
        if isinstance(value, (list, tuple)) and len(value) >= 2 and all(isinstance(n, (int, float)) for n in value[:2]):
            points.append([float(value[0]), float(value[1])])
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item)
    if geometry.get("type") == "Feature":
        geometry = geometry.get("geometry") or {}
    elif geometry.get("type") == "FeatureCollection":
        for feature in geometry.get("features") or []:
            if isinstance(feature, dict):
                walk((feature.get("geometry") or {}).get("coordinates"))
    else:
        walk(geometry.get("coordinates", geometry))
    if not points:
        raise BhoonidhiError("Invalid GeoJSON geometry: no coordinates")
    xs, ys = zip(*points)
    return [min(xs), min(ys), max(xs), max(ys)]


def _normalize_product(feature: Dict[str, Any], fallback_date: str) -> Dict[str, Any]:
    props = feature.get("properties") or {}
    return {"id": feature.get("id"), "date": (props.get("datetime") or props.get("startDate") or fallback_date)[:10], "satellite": "Sentinel-1A", "polarisation": props.get("polarisation", "VV, VH"), "source": "Bhoonidhi", "online": props.get("Online"), "properties": props, "feature": feature}


_default_client = BhoonidhiClient()


async def get_bhoonidhi_client() -> BhoonidhiClient:
    return _default_client
