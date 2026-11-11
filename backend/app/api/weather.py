import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.field import Field
from app.schemas.weather import WeatherResponse
from app.services.weather_service import WeatherService

logger = logging.getLogger("agrisense.api.weather")

router = APIRouter(prefix="/weather", tags=["Weather Intelligence"])


@router.get("/forecast", response_model=WeatherResponse)
async def get_weather_forecast(
    latitude: float = Query(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees"),
    longitude: float = Query(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees"),
    field_id: Optional[str] = Query(None, description="Optional active AgriSense field ID"),
    refresh: bool = Query(False, description="Force fresh fetch bypassing memory cache"),
    db: Session = Depends(get_db),
) -> WeatherResponse:
    """
    Get comprehensive Open-Meteo ECMWF IFS HRES forecast with agricultural,
    atmospheric, solar, wind, and irrigation intelligence.
    """
    location_meta = {}

    # If field_id is supplied, enrich response with field database context
    if field_id:
        try:
            field = db.query(Field).filter(Field.field_id == field_id).first()
            if field:
                location_meta = {
                    "field_id": field.field_id,
                    "field_name": field.field_name or f"Field {field.field_id}",
                    "village": field.village,
                    "tehsil": field.tehsil or field.block,
                    "district": field.district,
                    "state": field.state,
                    "country": field.country or "India",
                    "area_hectares": field.area_hectares,
                    "area_acres": field.area_acres,
                }
        except Exception as exc:
            logger.warning("Could not query field %s from database: %s", field_id, exc)

    try:
        forecast = await WeatherService.get_forecast(
            latitude=latitude,
            longitude=longitude,
            location_meta=location_meta,
            force_refresh=refresh,
        )
        return forecast
    except Exception as exc:
        logger.exception("Weather forecast retrieval failed for (%s, %s): %s", latitude, longitude, exc)
        raise HTTPException(
            status_code=503,
            detail=f"Weather service temporarily unavailable: {str(exc)}",
        ) from exc
