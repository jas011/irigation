import base64
import io
import json
import logging
import math
from typing import Optional, Dict, Any, Tuple, List
import httpx
from PIL import Image, ImageDraw
from fastapi import HTTPException, status

from app.core.config import settings
from app.schemas.field import GeoJSONPolygon, FieldAIVerificationResponse

logger = logging.getLogger(__name__)

CATEGORY_MAP = {
    "agricultural_field": "Agricultural Farmland",
    "farmland": "Agricultural Farmland",
    "crop_field": "Agricultural Farmland",
    "orchard": "Agricultural Orchard / Grove",
    "residential_urban": "Residential / Urban Area",
    "residential": "Residential / Buildings",
    "urban": "Urban / Built-up Area",
    "buildings": "Residential / Buildings",
    "roads": "Roads / Transportation Network",
    "road": "Roads / Transportation Network",
    "water_body": "River / Water Body",
    "river": "River / Water Body",
    "riverbed": "River / Riverbed / Sandbar",
    "water": "River / Water Body",
    "wetlands": "Wetlands / Water Body",
    "forest_natural": "Dense Forest / Natural Trees",
    "forest": "Dense Trees / Forest",
    "trees": "Dense Trees / Forest",
    "industrial": "Industrial / Commercial Area",
    "commercial": "Commercial / Industrial Area",
    "barren_wasteland": "Barren / Sandy Wasteland",
    "barren_land": "Barren / Non-Agricultural Land",
    "construction": "Construction / Excavation Site",
}


def _deg2num(lat_deg: float, lon_deg: float, zoom: int) -> Tuple[int, int]:
    lat_rad = math.radians(lat_deg)
    n = 1 << zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (xtile, ytile)


class FieldAIVerificationService:
    @staticmethod
    def _compute_bbox(geometry: GeoJSONPolygon, pad_ratio: float = 0.25) -> Tuple[float, float, float, float]:
        coords = geometry.coordinates[0]
        lons = [float(pt[0]) for pt in coords]
        lats = [float(pt[1]) for pt in coords]

        min_lon, max_lon = min(lons), max(lons)
        min_lat, max_lat = min(lats), max(lats)

        # Ensure minimum span of ~200m
        lon_span = max(max_lon - min_lon, 0.002)
        lat_span = max(max_lat - min_lat, 0.002)

        pad_x = lon_span * pad_ratio
        pad_y = lat_span * pad_ratio

        return (min_lon - pad_x, min_lat - pad_y, max_lon + pad_x, max_lat + pad_y)

    @staticmethod
    async def _fetch_from_export_api(bbox: Tuple[float, float, float, float], width: int = 800, height: int = 800) -> Optional[bytes]:
        """
        Attempts to fetch satellite imagery using ArcGIS World Imagery export endpoint.
        Tries multiple formats/sizes before failing.
        """
        formats_to_try = [
            f"size={width},{height}&format=jpg",
            f"size=512,512&format=jpg",
            f"size=512,512&format=png24"
        ]

        async with httpx.AsyncClient(timeout=15.0) as client:
            for fmt_query in formats_to_try:
                arcgis_url = (
                    f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/export"
                    f"?bbox={bbox[0]:.6f},{bbox[1]:.6f},{bbox[2]:.6f},{bbox[3]:.6f}"
                    f"&bboxSR=4326&imageSR=4326&{fmt_query}&f=image"
                )
                try:
                    resp = await client.get(arcgis_url)
                    if resp.status_code == 200 and len(resp.content) > 1000:
                        return resp.content
                except Exception as exc:
                    logger.debug("ArcGIS export format %s failed: %s", fmt_query, exc)
        return None

    @staticmethod
    async def _fetch_from_tile_service(center_lat: float, center_lon: float, zoom: int = 16) -> Image.Image:
        """
        Reliable fallback that fetches standard tiles directly from ArcGIS CDN tile cache.
        """
        center_x, center_y = _deg2num(center_lat, center_lon, zoom)
        tiles = [
            (center_x, center_y),
            (center_x + 1, center_y),
            (center_x, center_y + 1),
            (center_x + 1, center_y + 1)
        ]

        stitched = Image.new("RGB", (512, 512), (30, 40, 30))
        async with httpx.AsyncClient(timeout=10.0) as client:
            for idx, (tx, ty) in enumerate(tiles):
                url = f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{zoom}/{ty}/{tx}"
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        tile_img = Image.open(io.BytesIO(resp.content)).convert("RGB")
                        px = (idx % 2) * 256
                        py = (idx // 2) * 256
                        stitched.paste(tile_img, (px, py))
                except Exception as exc:
                    logger.debug("Tile fetch failed for %s/%s/%s: %s", zoom, ty, tx, exc)

        return stitched

    @classmethod
    async def fetch_and_annotate_satellite_image(
        cls, 
        geometry: GeoJSONPolygon, 
        width: int = 800, 
        height: int = 800
    ) -> str:
        """
        Fetches satellite imagery (via export with tile fallback) and draws the user-drawn
        polygon boundary onto the image so OpenAI Vision evaluates the exact selected area.
        """
        bbox = cls._compute_bbox(geometry, pad_ratio=0.25)
        raw_bytes = await cls._fetch_from_export_api(bbox, width=width, height=height)

        if raw_bytes:
            base_img = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")
            img_width, img_height = base_img.size
        else:
            logger.info("ArcGIS export failed; using tile server fallback.")
            coords = geometry.coordinates[0]
            center_lon = sum(pt[0] for pt in coords) / len(coords)
            center_lat = sum(pt[1] for pt in coords) / len(coords)
            stitched_img = await cls._fetch_from_tile_service(center_lat, center_lon, zoom=16)
            base_img = stitched_img.convert("RGBA")
            img_width, img_height = base_img.size

        try:
            overlay = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)

            coords = geometry.coordinates[0]
            pts = [
                (
                    ((pt[0] - bbox[0]) / (bbox[2] - bbox[0])) * img_width,
                    ((bbox[3] - pt[1]) / (bbox[3] - bbox[1])) * img_height
                )
                for pt in coords
            ]

            # Red fill with subtle transparency and clear red border
            draw.polygon(pts, fill=(255, 0, 0, 40), outline=(255, 20, 20, 255), width=4)

            annotated_img = Image.alpha_composite(base_img, overlay).convert("RGB")
            buf = io.BytesIO()
            annotated_img.save(buf, format="JPEG", quality=92)
            return base64.b64encode(buf.getvalue()).decode("utf-8")
        except Exception as e:
            logger.warning("Failed to overlay boundary outline (%s); saving base image.", e)
            buf = io.BytesIO()
            base_img.convert("RGB").save(buf, format="JPEG", quality=90)
            return base64.b64encode(buf.getvalue()).decode("utf-8")

    @classmethod
    async def verify_field(
        cls, 
        geometry: GeoJSONPolygon, 
        image_base64: Optional[str] = None
    ) -> FieldAIVerificationResponse:
        """
        Validates whether the selected region appears to be an actual agricultural/farmland field
        using OpenAI Vision with multi-possibility probabilistic evaluation.
        """
        api_key = settings.OPENAI_API_KEY
        if not api_key or not api_key.strip():
            logger.error("OPENAI_API_KEY is not configured in backend environment.")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI Field Verification service is currently unavailable (API key not configured)."
            )

        # 1. Obtain annotated satellite image
        b64_image = image_base64
        if not b64_image:
            b64_image = await cls.fetch_and_annotate_satellite_image(geometry)

        # 2. Prepare OpenAI Vision request
        model = settings.OPENAI_MODEL or "gpt-4o-mini"
        confidence_threshold = getattr(settings, "OPENAI_CONFIDENCE_THRESHOLD", 0.65)

        system_instruction = (
            "You are a rigorous, highly accurate satellite remote sensing imagery expert specializing in agricultural land validation.\n"
            "Your job is to inspect the user-selected region highlighted inside the RED BOUNDARY OUTLINE on the satellite imagery "
            "and determine its exact land cover classification across ALL possibilities.\n\n"
            "CRITICAL DISCRIMINATION RULES:\n"
            "1. RIVERS, RIVERBEDS & WATER BODIES (e.g. Satluj/Sutlej River, water channels, canals, floodplains, sandbars, reservoirs, wetlands):\n"
            "   - Look for meandering braided channels, dark/greenish/murky water streams, sandy or silt riverbanks, riparian sandbars, dry riverbeds, wetlands, or floodways.\n"
            "   - If the region spans across or inside a river, riverbed, sandbar, water surface, lake, or canal, it is STRICTLY a 'water_body'.\n"
            "   - Under NO circumstance should a river, river channel, sandbar, or floodplain be marked as an agricultural field.\n\n"
            "2. RESIDENTIAL & URBAN INFRASTRUCTURE:\n"
            "   - Houses, buildings, rooftops, roads, streets, pavement, dense settlements.\n"
            "   - Strictly classified as 'residential_urban'.\n\n"
            "3. FOREST & NATURAL VEGETATION:\n"
            "   - Dense wild trees, unmanaged forest, jungles, scrubland without field boundaries.\n"
            "   - Strictly classified as 'forest_natural'.\n\n"
            "4. BARREN & WASTELAND:\n"
            "   - Rocky terrain, dry non-arable wasteland, desert, industrial excavation.\n"
            "   - Strictly classified as 'barren_wasteland'.\n\n"
            "5. AGRICULTURAL FARMLAND:\n"
            "   - Must have clear regular rectangular cadastral field plots, distinct tilled soil plots, structured crop rows, or partitioned farm beds.\n"
            "   - Only true farmland parcels qualify.\n\n"
            "Analyze all possibilities and assign probability scores (between 0.0 and 1.0) summing to ~1.0.\n\n"
            "Respond strictly in valid JSON format:\n"
            "{\n"
            '  "is_field": boolean,\n'
            '  "confidence": number (between 0.0 and 1.0),\n'
            '  "primary_land_type": "water_body" | "residential_urban" | "forest_natural" | "barren_wasteland" | "industrial" | "agricultural_field",\n'
            '  "user_friendly_category": string,\n'
            '  "all_possibilities": {\n'
            '    "water_body": number,\n'
            '    "agricultural_field": number,\n'
            '    "residential_urban": number,\n'
            '    "forest_natural": number,\n'
            '    "barren_wasteland": number\n'
            '  },\n'
            '  "visual_features_observed": [string],\n'
            '  "reason": string (1 concise sentence explaining why the region is or is not an agricultural field)\n'
            "}"
        )

        user_prompt = "Analyze the land cover strictly inside the highlighted red polygon boundary. Check all possibilities including rivers/water bodies, urban areas, or farm plots. Return JSON."

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": system_instruction
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{b64_image}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
            "max_tokens": 400
        }

        # 3. Invoke OpenAI Vision API
        try:
            async with httpx.AsyncClient(timeout=35.0) as client:
                res = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json=payload
                )

            if res.status_code != 200:
                logger.error("OpenAI Vision API error %s: %s", res.status_code, res.text)
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="AI validation service encountered an unexpected error. Please try again."
                )

            data = res.json()
            content_str = data["choices"][0]["message"]["content"]
            result_json = json.loads(content_str)

            raw_is_field = bool(result_json.get("is_field", False))
            confidence = float(result_json.get("confidence", 0.0))
            primary_land_type = str(result_json.get("primary_land_type", "unknown")).lower().strip()
            reason = str(result_json.get("reason", "")).strip()
            all_possibilities = result_json.get("all_possibilities", {})
            visual_features = result_json.get("visual_features_observed", [])

            # Strict validation checks
            water_prob = float(all_possibilities.get("water_body", 0.0))
            urban_prob = float(all_possibilities.get("residential_urban", all_possibilities.get("residential", 0.0)))

            is_agricultural = (
                primary_land_type == "agricultural_field" and
                raw_is_field and
                confidence >= confidence_threshold and
                water_prob < 0.20 and
                urban_prob < 0.25
            )

            # Map category to user-friendly label
            normalized_key = primary_land_type.replace(" ", "_").replace("-", "_")
            user_friendly_cat = result_json.get("user_friendly_category")
            if not user_friendly_cat:
                user_friendly_cat = CATEGORY_MAP.get(
                    normalized_key, 
                    primary_land_type.replace("_", " ").title() if primary_land_type else "Non-Agricultural Area"
                )

            return FieldAIVerificationResponse(
                is_field=is_agricultural,
                confidence=round(confidence if is_agricultural else max(confidence, water_prob, urban_prob, 0.8), 2),
                land_type=primary_land_type,
                reason=reason or ("The region corresponds to agricultural farmland." if is_agricultural else "The selected region is not an agricultural field."),
                user_friendly_category=user_friendly_cat,
                all_possibilities=all_possibilities,
                visual_features_observed=visual_features,
                details={
                    "model": model,
                    "raw_is_field": raw_is_field,
                    "threshold_applied": confidence_threshold
                }
            )

        except HTTPException:
            raise
        except json.JSONDecodeError as jde:
            logger.error("Failed to parse OpenAI JSON output: %s", jde)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI validation returned an unreadable response format. Please retry."
            )
        except httpx.TimeoutException:
            logger.error("Timeout connecting to OpenAI API.")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="AI field validation timed out. Please check your internet connection and retry."
            )
        except Exception as e:
            logger.exception("Unexpected error during AI field verification: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred while verifying the field with AI."
            )
