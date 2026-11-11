import logging
import math
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx
from cachetools import TTLCache

from app.schemas.weather import (
    AgriculturalWeather,
    AtmosphericConditions,
    CurrentWeather,
    DailyForecastItem,
    HourlyForecastItem,
    IrrigationOutlook,
    LocationContext,
    ModelMetadata,
    SoilMoistureDepth,
    SoilTemperatureDepth,
    SolarConditions,
    TimelinePeriod,
    WeatherAlert,
    WeatherConditionInfo,
    WeatherResponse,
    WindConditions,
)

logger = logging.getLogger("agrisense.weather_service")

# In-memory cache for weather forecasts: 15 minutes TTL, max 500 coordinates
_weather_cache = TTLCache(maxsize=500, ttl=900)

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
HTTP_TIMEOUT_SECONDS = 15.0

# Indian Standard Timezone (UTC + 5:30)
IST_TZ = timezone(timedelta(hours=5, minutes=30))


def _get_cardinal_direction(degrees: float) -> str:
    val = int((degrees / 22.5) + 0.5)
    cardinals = [
        "N", "NNE", "NE", "ENE",
        "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW",
        "W", "WNW", "NW", "NNW"
    ]
    return cardinals[val % 16]


def _get_beaufort_description(speed_kmh: float) -> str:
    if speed_kmh < 2:
        return "Calm"
    elif speed_kmh < 6:
        return "Light Air"
    elif speed_kmh < 12:
        return "Light Breeze"
    elif speed_kmh < 20:
        return "Gentle Breeze"
    elif speed_kmh < 29:
        return "Moderate Breeze"
    elif speed_kmh < 39:
        return "Fresh Breeze"
    elif speed_kmh < 50:
        return "Strong Breeze"
    elif speed_kmh < 62:
        return "High Wind / Moderate Gale"
    elif speed_kmh < 75:
        return "Gale"
    else:
        return "Severe Gale / Storm Force"


def _decode_wmo_code(code: int, is_day: bool = True) -> WeatherConditionInfo:
    """
    Decodes WMO Weather interpretation codes (WW) into human readable labels
    and animation / icon triggers.
    """
    wmo_map: Dict[int, Tuple[str, str, str]] = {
        0: ("Clear Sky", "Clear blue sky with bright sunshine", "sunny" if is_day else "clear_night"),
        1: ("Mainly Clear", "Mainly clear sky with slight cloud presence", "mostly_sunny" if is_day else "clear_night"),
        2: ("Partly Cloudy", "Scattered clouds with intermittent sunshine", "partly_cloudy" if is_day else "partly_cloudy_night"),
        3: ("Overcast", "Overcast sky with dense cloud coverage", "cloudy"),
        45: ("Foggy", "Dense fog reducing ground visibility", "fog"),
        48: ("Depositing Rime Fog", "Freezing rime fog with icy condensation", "fog"),
        51: ("Light Drizzle", "Light intermittent drizzle", "drizzle"),
        53: ("Moderate Drizzle", "Continuous moderate drizzle", "drizzle"),
        55: ("Dense Drizzle", "Heavy dense drizzle", "drizzle"),
        56: ("Light Freezing Drizzle", "Light freezing drizzle", "drizzle"),
        57: ("Dense Freezing Drizzle", "Dense freezing drizzle", "drizzle"),
        61: ("Slight Rain", "Light rain showers", "rain"),
        62: ("Rain", "Steady moderate rainfall", "rain"),
        63: ("Moderate Rain", "Moderate sustained rainfall", "rain"),
        65: ("Heavy Rain", "Intense heavy rainfall", "heavy_rain"),
        66: ("Light Freezing Rain", "Light freezing rain", "rain"),
        67: ("Heavy Freezing Rain", "Heavy freezing rain", "heavy_rain"),
        71: ("Slight Snow", "Light snowfall", "snow"),
        73: ("Moderate Snow", "Moderate continuous snowfall", "snow"),
        75: ("Heavy Snow", "Heavy dense snowfall", "snow"),
        77: ("Snow Grains", "Fine crystalline snow grains", "snow"),
        80: ("Light Rain Showers", "Scattered light rain showers", "rain"),
        81: ("Moderate Rain Showers", "Frequent moderate rain showers", "rain"),
        82: ("Violent Rain Showers", "Torrential rain showers", "heavy_rain"),
        85: ("Slight Snow Showers", "Scattered light snow showers", "snow"),
        86: ("Heavy Snow Showers", "Heavy continuous snow showers", "snow"),
        95: ("Thunderstorm", "Active thunderstorm with lightning and rain", "thunderstorm"),
        96: ("Thunderstorm with Slight Hail", "Severe thunderstorm with slight hail", "thunderstorm"),
        99: ("Thunderstorm with Heavy Hail", "Severe thunderstorm with heavy hail", "thunderstorm"),
    }

    if code in wmo_map:
        label, desc, icon_type = wmo_map[code]
    else:
        label, desc, icon_type = ("Partly Cloudy", "Partly cloudy conditions", "partly_cloudy" if is_day else "partly_cloudy_night")

    return WeatherConditionInfo(
        code=code,
        label=label,
        description=desc,
        icon_type=icon_type,
        is_day=is_day,
    )


def _calculate_vpd_kpa(temp_c: float, rh_percent: float) -> float:
    """
    Calculates Vapor Pressure Deficit (VPD) in kPa using Tetens FAO equation.
    e_s = 0.61078 * exp((17.27 * T) / (T + 237.3))
    e_a = e_s * (RH / 100)
    VPD = e_s - e_a
    """
    if temp_c is None or rh_percent is None:
        return 0.0
    es = 0.61078 * math.exp((17.27 * temp_c) / (temp_c + 237.3))
    ea = es * (max(0.0, min(100.0, rh_percent)) / 100.0)
    vpd = max(0.0, es - ea)
    return round(vpd, 2)


def _get_vpd_status_and_explanation(vpd_kpa: float) -> Tuple[str, str]:
    if vpd_kpa < 0.4:
        return (
            "Low (Fungal Risk)",
            "Atmospheric moisture demand is minimal. Plant transpiration is reduced, increasing risk of foliar disease & fungal pathogens."
        )
    elif vpd_kpa <= 1.2:
        return (
            "Optimal Transpiration",
            "Ideal atmospheric demand. Crop stomata remain open for efficient photosynthesis and nutrient uptake without moisture stress."
        )
    elif vpd_kpa <= 1.6:
        return (
            "Moderate Water Demand",
            "Elevated atmospheric dryness. Transpiration rate is high; soil moisture depletion will accelerate."
        )
    elif vpd_kpa <= 2.2:
        return (
            "High Stress",
            "High atmospheric demand. Stomata begin protective closure; risk of leaf wilting and temporary growth slowdown."
        )
    else:
        return (
            "Severe Stress",
            "Critical atmospheric moisture deficit. Severe crop moisture stress; urgent protective irrigation needed if soil is dry."
        )


def _classify_soil_moisture_m3m3(val: float) -> Tuple[float, str]:
    # Typical agricultural soil volumetric water content:
    # < 0.15 m3/m3: Dry / Wilting Point
    # 0.15 - 0.25: Moderate Deficit
    # 0.25 - 0.38: Adequate / Field Capacity range
    # > 0.38: Near Saturation
    pct = round(min(100.0, max(0.0, (val / 0.45) * 100)), 1)
    if val < 0.15:
        status = "Dry (Below Refill Point)"
    elif val < 0.25:
        status = "Moderate Deficit"
    elif val < 0.38:
        status = "Adequate (Field Capacity)"
    else:
        status = "Saturated"
    return pct, status


class WeatherService:
    @staticmethod
    async def get_forecast(
        latitude: float,
        longitude: float,
        location_meta: Optional[Dict[str, Any]] = None,
        force_refresh: bool = False,
    ) -> WeatherResponse:
        """
        Fetches and normalizes high-resolution ECMWF IFS weather forecast from Open-Meteo.
        """
        # Round coordinates to 4 decimal places for cache consistency (~11 meters)
        cache_lat = round(latitude, 4)
        cache_lon = round(longitude, 4)
        cache_key = f"ecmwf_{cache_lat}_{cache_lon}"

        if not force_refresh and cache_key in _weather_cache:
            cached_data: WeatherResponse = _weather_cache[cache_key]
            # Update location meta if new context provided
            if location_meta:
                cached_data.location = WeatherService._build_location_context(latitude, longitude, location_meta)
            cached_data.metadata.cached = True
            return cached_data

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": [
                "temperature_2m",
                "relative_humidity_2m",
                "apparent_temperature",
                "is_day",
                "precipitation",
                "rain",
                "showers",
                "snowfall",
                "weather_code",
                "cloud_cover",
                "pressure_msl",
                "surface_pressure",
                "wind_speed_10m",
                "wind_direction_10m",
                "wind_gusts_10m",
            ],
            "hourly": [
                "temperature_2m",
                "relative_humidity_2m",
                "dew_point_2m",
                "apparent_temperature",
                "precipitation_probability",
                "precipitation",
                "rain",
                "showers",
                "snowfall",
                "weather_code",
                "pressure_msl",
                "surface_pressure",
                "cloud_cover",
                "visibility",
                "evapotranspiration",
                "et0_fao_evapotranspiration",
                "vapour_pressure_deficit",
                "wind_speed_10m",
                "wind_direction_10m",
                "wind_gusts_10m",
                "soil_temperature_0cm",
                "soil_temperature_6cm",
                "soil_temperature_18cm",
                "soil_temperature_54cm",
                "soil_moisture_0_to_1cm",
                "soil_moisture_1_to_3cm",
                "soil_moisture_3_to_9cm",
                "soil_moisture_9_to_27cm",
                "soil_moisture_27_to_81cm",
                "shortwave_radiation",
                "direct_radiation",
                "diffuse_radiation",
                "uv_index",
            ],
            "daily": [
                "weather_code",
                "temperature_2m_max",
                "temperature_2m_min",
                "apparent_temperature_max",
                "apparent_temperature_min",
                "sunrise",
                "sunset",
                "daylight_duration",
                "sunshine_duration",
                "uv_index_max",
                "precipitation_sum",
                "rain_sum",
                "showers_sum",
                "snowfall_sum",
                "precipitation_hours",
                "precipitation_probability_max",
                "wind_speed_10m_max",
                "wind_gusts_10m_max",
                "wind_direction_10m_dominant",
                "shortwave_radiation_sum",
                "et0_fao_evapotranspiration",
            ],
            "timezone": "Asia/Kolkata",
            "models": "ecmwf_ifs025",
            "forecast_days": 10,
        }

        start_time = time.perf_counter()
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            try:
                response = await client.get(OPEN_METEO_FORECAST_URL, params=params)
                response.raise_for_status()
                raw_data = response.json()
            except httpx.HTTPError as exc:
                logger.error("Open-Meteo ECMWF API request failed for (%s, %s): %s", latitude, longitude, exc)
                # Fallback to standard Open-Meteo best_match if ecmwf_ifs025 has temporary outage
                try:
                    params_fallback = params.copy()
                    params_fallback.pop("models", None)
                    response = await client.get(OPEN_METEO_FORECAST_URL, params=params_fallback)
                    response.raise_for_status()
                    raw_data = response.json()
                except Exception as inner_exc:
                    logger.exception("Fallback forecast request also failed: %s", inner_exc)
                    raise RuntimeError(f"Weather provider temporarily unavailable: {exc}") from exc

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        parsed_response = WeatherService._normalize_payload(raw_data, latitude, longitude, elapsed_ms, location_meta)

        # Store in cache
        _weather_cache[cache_key] = parsed_response
        return parsed_response

    @staticmethod
    def _build_location_context(latitude: float, longitude: float, meta: Optional[Dict[str, Any]]) -> LocationContext:
        meta = meta or {}
        return LocationContext(
            field_id=str(meta.get("field_id") or meta.get("id") or "") or None,
            field_name=meta.get("name") or meta.get("field_name") or None,
            village=meta.get("village") or None,
            tehsil=meta.get("tehsil") or meta.get("block") or None,
            district=meta.get("district") or None,
            state=meta.get("state") or None,
            country=meta.get("country") or "India",
            area_hectares=meta.get("area_hectares"),
            area_acres=meta.get("area_acres"),
            latitude=latitude,
            longitude=longitude,
        )

    @staticmethod
    def _normalize_payload(
        data: Dict[str, Any],
        latitude: float,
        longitude: float,
        fetch_ms: float,
        location_meta: Optional[Dict[str, Any]] = None,
    ) -> WeatherResponse:
        current_raw = data.get("current", {})
        hourly_raw = data.get("hourly", {})
        daily_raw = data.get("daily", {})

        now_ist_str = datetime.now(IST_TZ).strftime("%Y-%m-%d %H:%M:%S IST")

        # 1. Location & Model Metadata
        location = WeatherService._build_location_context(latitude, longitude, location_meta)
        metadata = ModelMetadata(
            provider="Open-Meteo",
            primary_model="ECMWF IFS HRES",
            grid_resolution="≈ 9 km (0.1° / 0.25°)",
            elevation_m=data.get("elevation"),
            latitude=data.get("latitude", latitude),
            longitude=data.get("longitude", longitude),
            timezone=data.get("timezone", "Asia/Kolkata"),
            timezone_abbreviation=data.get("timezone_abbreviation", "IST"),
            generation_time_ms=data.get("generationtime_ms", fetch_ms),
            cached=False,
            fetched_at_ist=now_ist_str,
        )

        # 2. Daily Forecast Items
        daily_items: List[DailyForecastItem] = []
        d_times = daily_raw.get("time", [])
        d_codes = daily_raw.get("weather_code", [])
        d_tmax = daily_raw.get("temperature_2m_max", [])
        d_tmin = daily_raw.get("temperature_2m_min", [])
        d_atmax = daily_raw.get("apparent_temperature_max", [])
        d_atmin = daily_raw.get("apparent_temperature_min", [])
        d_sunrise = daily_raw.get("sunrise", [])
        d_sunset = daily_raw.get("sunset", [])
        d_daylight = daily_raw.get("daylight_duration", [])
        d_sunshine = daily_raw.get("sunshine_duration", [])
        d_uvmax = daily_raw.get("uv_index_max", [])
        d_precip_sum = daily_raw.get("precipitation_sum", [])
        d_rain_sum = daily_raw.get("rain_sum", [])
        d_showers_sum = daily_raw.get("showers_sum", [])
        d_snow_sum = daily_raw.get("snowfall_sum", [])
        d_precip_hours = daily_raw.get("precipitation_hours", [])
        d_precip_prob_max = daily_raw.get("precipitation_probability_max", [])
        d_wspeed_max = daily_raw.get("wind_speed_10m_max", [])
        d_wgust_max = daily_raw.get("wind_gusts_10m_max", [])
        d_wdir_dom = daily_raw.get("wind_direction_10m_dominant", [])
        d_et0_sum = daily_raw.get("et0_fao_evapotranspiration", [])
        d_rad_sum = daily_raw.get("shortwave_radiation_sum", [])

        for idx, date_str in enumerate(d_times):
            try:
                dt_obj = datetime.strptime(date_str, "%Y-%m-%d")
                day_name = dt_obj.strftime("%A")
                fmt_date = dt_obj.strftime("%d %b %Y")
            except Exception:
                day_name = "Day"
                fmt_date = date_str

            code = d_codes[idx] if idx < len(d_codes) else 0
            w_cond = _decode_wmo_code(code, is_day=True)
            wdir = float(d_wdir_dom[idx]) if idx < len(d_wdir_dom) and d_wdir_dom[idx] is not None else 0.0

            daily_items.append(
                DailyForecastItem(
                    date=date_str,
                    day_name=day_name,
                    formatted_date=fmt_date,
                    weather_code=code,
                    condition=w_cond,
                    temp_max=round(float(d_tmax[idx]), 1) if idx < len(d_tmax) and d_tmax[idx] is not None else 0.0,
                    temp_min=round(float(d_tmin[idx]), 1) if idx < len(d_tmin) and d_tmin[idx] is not None else 0.0,
                    apparent_temp_max=round(float(d_atmax[idx]), 1) if idx < len(d_atmax) and d_atmax[idx] is not None else 0.0,
                    apparent_temp_min=round(float(d_atmin[idx]), 1) if idx < len(d_atmin) and d_atmin[idx] is not None else 0.0,
                    sunrise=d_sunrise[idx] if idx < len(d_sunrise) else "",
                    sunset=d_sunset[idx] if idx < len(d_sunset) else "",
                    daylight_duration_hours=round(float(d_daylight[idx]) / 3600.0, 1) if idx < len(d_daylight) and d_daylight[idx] is not None else 0.0,
                    sunshine_duration_hours=round(float(d_sunshine[idx]) / 3600.0, 1) if idx < len(d_sunshine) and d_sunshine[idx] is not None else 0.0,
                    uv_index_max=round(float(d_uvmax[idx]), 1) if idx < len(d_uvmax) and d_uvmax[idx] is not None else 0.0,
                    precipitation_sum=round(float(d_precip_sum[idx]), 1) if idx < len(d_precip_sum) and d_precip_sum[idx] is not None else 0.0,
                    rain_sum=round(float(d_rain_sum[idx]), 1) if idx < len(d_rain_sum) and d_rain_sum[idx] is not None else 0.0,
                    showers_sum=round(float(d_showers_sum[idx]), 1) if idx < len(d_showers_sum) and d_showers_sum[idx] is not None else 0.0,
                    snowfall_sum=round(float(d_snow_sum[idx]), 1) if idx < len(d_snow_sum) and d_snow_sum[idx] is not None else 0.0,
                    precipitation_hours=round(float(d_precip_hours[idx]), 1) if idx < len(d_precip_hours) and d_precip_hours[idx] is not None else 0.0,
                    precipitation_probability_max=int(d_precip_prob_max[idx]) if idx < len(d_precip_prob_max) and d_precip_prob_max[idx] is not None else 0,
                    wind_speed_max=round(float(d_wspeed_max[idx]), 1) if idx < len(d_wspeed_max) and d_wspeed_max[idx] is not None else 0.0,
                    wind_gusts_max=round(float(d_wgust_max[idx]), 1) if idx < len(d_wgust_max) and d_wgust_max[idx] is not None else 0.0,
                    wind_direction_dominant=int(wdir),
                    wind_direction_cardinal=_get_cardinal_direction(wdir),
                    et0_fao_sum=round(float(d_et0_sum[idx]), 2) if idx < len(d_et0_sum) and d_et0_sum[idx] is not None else None,
                    shortwave_radiation_sum=round(float(d_rad_sum[idx]), 1) if idx < len(d_rad_sum) and d_rad_sum[idx] is not None else None,
                )
            )

        # 3. Hourly Forecast Items (up to 72 hours)
        hourly_items: List[HourlyForecastItem] = []
        h_times = hourly_raw.get("time", [])
        h_temp = hourly_raw.get("temperature_2m", [])
        h_rh = hourly_raw.get("relative_humidity_2m", [])
        h_dew = hourly_raw.get("dew_point_2m", [])
        h_atemp = hourly_raw.get("apparent_temperature", [])
        h_pprob = hourly_raw.get("precipitation_probability", [])
        h_precip = hourly_raw.get("precipitation", [])
        h_rain = hourly_raw.get("rain", [])
        h_showers = hourly_raw.get("showers", [])
        h_snow = hourly_raw.get("snowfall", [])
        h_code = hourly_raw.get("weather_code", [])
        h_pmsl = hourly_raw.get("pressure_msl", [])
        h_psurf = hourly_raw.get("surface_pressure", [])
        h_cloud = hourly_raw.get("cloud_cover", [])
        h_vis = hourly_raw.get("visibility", [])
        h_et = hourly_raw.get("evapotranspiration", [])
        h_et0 = hourly_raw.get("et0_fao_evapotranspiration", [])
        h_vpd = hourly_raw.get("vapour_pressure_deficit", [])
        h_wspeed = hourly_raw.get("wind_speed_10m", [])
        h_wdir = hourly_raw.get("wind_direction_10m", [])
        h_wgust = hourly_raw.get("wind_gusts_10m", [])
        h_uv = hourly_raw.get("uv_index", [])
        h_rad_dir = hourly_raw.get("direct_radiation", [])
        h_rad_sw = hourly_raw.get("shortwave_radiation", [])
        h_soil_m0 = hourly_raw.get("soil_moisture_0_to_1cm", [])
        h_soil_t0 = hourly_raw.get("soil_temperature_0cm", [])

        # Find current hour index to start hourly forecast
        now_dt = datetime.now(IST_TZ)
        now_hour_prefix = now_dt.strftime("%Y-%m-%dT%H:00")
        start_hour_idx = 0
        for idx, t in enumerate(h_times):
            if t >= now_hour_prefix:
                start_hour_idx = max(0, idx)
                break

        # Collect next 48 to 72 hours from current
        end_hour_idx = min(len(h_times), start_hour_idx + 48)

        for i in range(start_hour_idx, end_hour_idx):
            t_str = h_times[i]
            # Parse hour for display
            try:
                hour_part = t_str.split("T")[1][:5]
            except Exception:
                hour_part = t_str

            code = h_code[i] if i < len(h_code) and h_code[i] is not None else 0
            # Determine is_day from hour
            try:
                hr_int = int(hour_part.split(":")[0])
                is_day_h = 6 <= hr_int < 19
            except Exception:
                is_day_h = True

            wdir = float(h_wdir[i]) if i < len(h_wdir) and h_wdir[i] is not None else 0.0
            t_c = float(h_temp[i]) if i < len(h_temp) and h_temp[i] is not None else 0.0
            rh_val = float(h_rh[i]) if i < len(h_rh) and h_rh[i] is not None else 50.0

            vpd_val = float(h_vpd[i]) if i < len(h_vpd) and h_vpd[i] is not None else _calculate_vpd_kpa(t_c, rh_val)

            hourly_items.append(
                HourlyForecastItem(
                    time=t_str,
                    hour_label=hour_part,
                    temperature=round(t_c, 1),
                    apparent_temperature=round(float(h_atemp[i]), 1) if i < len(h_atemp) and h_atemp[i] is not None else round(t_c, 1),
                    relative_humidity=int(rh_val),
                    dew_point=round(float(h_dew[i]), 1) if i < len(h_dew) and h_dew[i] is not None else None,
                    precipitation_probability=int(h_pprob[i]) if i < len(h_pprob) and h_pprob[i] is not None else 0,
                    precipitation=round(float(h_precip[i]), 1) if i < len(h_precip) and h_precip[i] is not None else 0.0,
                    rain=round(float(h_rain[i]), 1) if i < len(h_rain) and h_rain[i] is not None else 0.0,
                    showers=round(float(h_showers[i]), 1) if i < len(h_showers) and h_showers[i] is not None else 0.0,
                    snowfall=round(float(h_snow[i]), 1) if i < len(h_snow) and h_snow[i] is not None else 0.0,
                    weather_code=code,
                    condition=_decode_wmo_code(code, is_day=is_day_h),
                    pressure_msl=round(float(h_pmsl[i]), 1) if i < len(h_pmsl) and h_pmsl[i] is not None else 1013.0,
                    surface_pressure=round(float(h_psurf[i]), 1) if i < len(h_psurf) and h_psurf[i] is not None else 1000.0,
                    cloud_cover=int(h_cloud[i]) if i < len(h_cloud) and h_cloud[i] is not None else 0,
                    visibility_km=round(float(h_vis[i]) / 1000.0, 1) if i < len(h_vis) and h_vis[i] is not None else None,
                    evapotranspiration=round(float(h_et[i]), 2) if i < len(h_et) and h_et[i] is not None else None,
                    et0=round(float(h_et0[i]), 2) if i < len(h_et0) and h_et0[i] is not None else None,
                    vpd_kpa=round(vpd_val, 2),
                    wind_speed=round(float(h_wspeed[i]), 1) if i < len(h_wspeed) and h_wspeed[i] is not None else 0.0,
                    wind_direction=int(wdir),
                    wind_direction_cardinal=_get_cardinal_direction(wdir),
                    wind_gusts=round(float(h_wgust[i]), 1) if i < len(h_wgust) and h_wgust[i] is not None else 0.0,
                    uv_index=round(float(h_uv[i]), 1) if i < len(h_uv) and h_uv[i] is not None else None,
                    direct_radiation=round(float(h_rad_dir[i]), 1) if i < len(h_rad_dir) and h_rad_dir[i] is not None else None,
                    shortwave_radiation=round(float(h_rad_sw[i]), 1) if i < len(h_rad_sw) and h_rad_sw[i] is not None else None,
                    soil_moisture_surface=round(float(h_soil_m0[i]), 3) if i < len(h_soil_m0) and h_soil_m0[i] is not None else None,
                    soil_temperature_surface=round(float(h_soil_t0[i]), 1) if i < len(h_soil_t0) and h_soil_t0[i] is not None else None,
                )
            )

        # 4. Current Weather
        cur_code = int(current_raw.get("weather_code", 0))
        cur_is_day = bool(current_raw.get("is_day", 1))
        cur_temp = round(float(current_raw.get("temperature_2m", 25.0)), 1)
        cur_atemp = round(float(current_raw.get("apparent_temperature", cur_temp)), 1)
        cur_rh = round(float(current_raw.get("relative_humidity_2m", 50.0)), 1)
        cur_wdir = float(current_raw.get("wind_direction_10m", 0.0))
        cur_wspeed = round(float(current_raw.get("wind_speed_10m", 10.0)), 1)
        cur_wgust = round(float(current_raw.get("wind_gusts_10m", 15.0)), 1)

        # Today max & min from first daily item
        today_tmax = daily_items[0].temp_max if daily_items else cur_temp + 4.0
        today_tmin = daily_items[0].temp_min if daily_items else cur_temp - 4.0
        today_pprob = daily_items[0].precipitation_probability_max if daily_items else 0

        # Current Dew Point from first hourly item
        cur_dew = hourly_items[0].dew_point if hourly_items else None

        current = CurrentWeather(
            time=current_raw.get("time", now_ist_str),
            temperature=cur_temp,
            apparent_temperature=cur_atemp,
            is_day=cur_is_day,
            relative_humidity=cur_rh,
            dew_point=cur_dew,
            precipitation=round(float(current_raw.get("precipitation", 0.0)), 1),
            rain=round(float(current_raw.get("rain", 0.0)), 1),
            showers=round(float(current_raw.get("showers", 0.0)), 1),
            snowfall=round(float(current_raw.get("snowfall", 0.0)), 1),
            cloud_cover=int(current_raw.get("cloud_cover", 20)),
            pressure_msl=round(float(current_raw.get("pressure_msl", 1013.0)), 1),
            surface_pressure=round(float(current_raw.get("surface_pressure", 1000.0)), 1),
            wind_speed=cur_wspeed,
            wind_direction=int(cur_wdir),
            wind_direction_cardinal=_get_cardinal_direction(cur_wdir),
            wind_gusts=cur_wgust,
            weather_code=cur_code,
            condition=_decode_wmo_code(cur_code, is_day=cur_is_day),
            temp_max_today=today_tmax,
            temp_min_today=today_tmin,
            precipitation_probability=today_pprob,
        )

        # 5. Agricultural Weather (Multi-depth soil moisture & temp, FAO ET0, VPD)
        cur_h_idx = start_hour_idx
        # Soil Moisture Depths (m3/m3)
        sm_0_1 = float(hourly_raw.get("soil_moisture_0_to_1cm", [0.25])[cur_h_idx] or 0.25)
        sm_1_3 = float(hourly_raw.get("soil_moisture_1_to_3cm", [0.27])[cur_h_idx] or 0.27)
        sm_3_9 = float(hourly_raw.get("soil_moisture_3_to_9cm", [0.29])[cur_h_idx] or 0.29)
        sm_9_27 = float(hourly_raw.get("soil_moisture_9_to_27cm", [0.31])[cur_h_idx] or 0.31)
        sm_27_81 = float(hourly_raw.get("soil_moisture_27_to_81cm", [0.33])[cur_h_idx] or 0.33)

        soil_moisture_levels = [
            SoilMoistureDepth(
                depth_label="0–1 cm (Surface)",
                depth_code="0-1cm",
                moisture_m3m3=round(sm_0_1, 3),
                moisture_percentage=_classify_soil_moisture_m3m3(sm_0_1)[0],
                status=_classify_soil_moisture_m3m3(sm_0_1)[1],
            ),
            SoilMoistureDepth(
                depth_label="1–3 cm (Seed Zone Top)",
                depth_code="1-3cm",
                moisture_m3m3=round(sm_1_3, 3),
                moisture_percentage=_classify_soil_moisture_m3m3(sm_1_3)[0],
                status=_classify_soil_moisture_m3m3(sm_1_3)[1],
            ),
            SoilMoistureDepth(
                depth_label="3–9 cm (Shallow Root Zone)",
                depth_code="3-9cm",
                moisture_m3m3=round(sm_3_9, 3),
                moisture_percentage=_classify_soil_moisture_m3m3(sm_3_9)[0],
                status=_classify_soil_moisture_m3m3(sm_3_9)[1],
            ),
            SoilMoistureDepth(
                depth_label="9–27 cm (Active Root Zone)",
                depth_code="9-27cm",
                moisture_m3m3=round(sm_9_27, 3),
                moisture_percentage=_classify_soil_moisture_m3m3(sm_9_27)[0],
                status=_classify_soil_moisture_m3m3(sm_9_27)[1],
            ),
            SoilMoistureDepth(
                depth_label="27–81 cm (Deep Subsoil)",
                depth_code="27-81cm",
                moisture_m3m3=round(sm_27_81, 3),
                moisture_percentage=_classify_soil_moisture_m3m3(sm_27_81)[0],
                status=_classify_soil_moisture_m3m3(sm_27_81)[1],
            ),
        ]

        # Soil Temperature Depths (°C)
        st_0 = float(hourly_raw.get("soil_temperature_0cm", [cur_temp])[cur_h_idx] or cur_temp)
        st_6 = float(hourly_raw.get("soil_temperature_6cm", [cur_temp - 1.0])[cur_h_idx] or cur_temp - 1.0)
        st_18 = float(hourly_raw.get("soil_temperature_18cm", [cur_temp - 2.0])[cur_h_idx] or cur_temp - 2.0)
        st_54 = float(hourly_raw.get("soil_temperature_54cm", [cur_temp - 3.0])[cur_h_idx] or cur_temp - 3.0)

        soil_temperatures = [
            SoilTemperatureDepth(depth_label="0 cm (Surface)", temperature_c=round(st_0, 1)),
            SoilTemperatureDepth(depth_label="6 cm (Seedbed)", temperature_c=round(st_6, 1)),
            SoilTemperatureDepth(depth_label="18 cm (Root Core)", temperature_c=round(st_18, 1)),
            SoilTemperatureDepth(depth_label="54 cm (Sub-Soil)", temperature_c=round(st_54, 1)),
        ]

        # ET0 Calculations
        et0_today = daily_items[0].et0_fao_sum if daily_items and daily_items[0].et0_fao_sum is not None else 4.5
        weekly_et0_sum = round(sum(d.et0_fao_sum or 0.0 for d in daily_items[:7]), 1) if daily_items else round(et0_today * 7, 1)

        if et0_today < 3.0:
            et0_interp = "Low atmospheric water demand. Low moisture loss expected today."
        elif et0_today < 5.5:
            et0_interp = "Moderate atmospheric water demand typical for growing season."
        elif et0_today < 7.5:
            et0_interp = "High atmospheric water demand. Significant crop transpiration and rapid soil moisture depletion."
        else:
            et0_interp = "Extreme atmospheric water demand. Heavy evaporative stress under intense solar radiation."

        et0_trend = []
        for d in daily_items[:7]:
            et0_trend.append({
                "date": d.formatted_date[:6],
                "day": d.day_name[:3],
                "et0": d.et0_fao_sum or 0.0,
                "rain": d.precipitation_sum,
            })

        # VPD
        cur_vpd = _calculate_vpd_kpa(cur_temp, cur_rh)
        vpd_status, vpd_expl = _get_vpd_status_and_explanation(cur_vpd)

        vpd_trend = []
        for h in hourly_items[:24]:
            vpd_trend.append({
                "time": h.hour_label,
                "vpd": h.vpd_kpa or 0.0,
                "temp": h.temperature,
            })

        agricultural = AgriculturalWeather(
            et0_today_mm=et0_today,
            et0_weekly_total_mm=weekly_et0_sum,
            et0_interpretation=et0_interp,
            et0_trend=et0_trend,
            soil_moisture_levels=soil_moisture_levels,
            soil_temperatures=soil_temperatures,
            current_vpd_kpa=cur_vpd,
            vpd_status=vpd_status,
            vpd_explanation=vpd_expl,
            vpd_trend=vpd_trend,
        )

        # 6. Irrigation Weather Outlook
        # 48h and 72h rainfall and ET0 sums
        rain_48h = round(sum(d.precipitation_sum for d in daily_items[:2]), 1) if len(daily_items) >= 2 else 0.0
        rain_72h = round(sum(d.precipitation_sum for d in daily_items[:3]), 1) if len(daily_items) >= 3 else rain_48h
        et0_48h = round(sum(d.et0_fao_sum or 0.0 for d in daily_items[:2]), 1) if len(daily_items) >= 2 else round(et0_today * 2, 1)
        et0_72h = round(sum(d.et0_fao_sum or 0.0 for d in daily_items[:3]), 1) if len(daily_items) >= 3 else round(et0_today * 3, 1)

        deficit_48h = round(et0_48h - rain_48h, 1)
        deficit_72h = round(et0_72h - rain_72h, 1)

        rain_prob_48h = max((d.precipitation_probability_max for d in daily_items[:2]), default=0)
        dry_days = sum(1 for d in daily_items[:7] if d.precipitation_sum < 1.0)

        # Classify risk level
        if rain_48h >= et0_48h + 5.0 or rain_prob_48h >= 70:
            risk_level = "LOW"
            advisory_hl = "Adequate precipitation expected; low immediate irrigation need."
            advisory_body = (
                f"Significant rainfall ({rain_48h} mm) is forecast over the next 48 hours with a {rain_prob_48h}% rain probability. "
                f"Atmospheric water balance remains positive. Delay scheduled supplemental irrigation to prevent waterlogging and fertilizer leaching."
            )
            field_actions = [
                "Postpone planned irrigation cycles for the next 48–72 hours.",
                "Ensure drainage channels and field bunds are clear to avoid standing water.",
                "Hold back scheduled top-dressing fertilizer applications until rain subsides."
            ]
        elif rain_48h > 2.0 or deficit_48h <= 4.0:
            risk_level = "MODERATE"
            advisory_hl = "Moderate atmospheric demand with minor rain probability."
            advisory_body = (
                f"Forecast rainfall is {rain_48h} mm against an atmospheric evaporative demand of {et0_48h} mm (48h deficit: {deficit_48h} mm). "
                "Monitor root-zone soil moisture closely and apply light maintenance irrigation if crops show early signs of moisture stress."
            )
            field_actions = [
                "Verify soil moisture readings in the 9–27 cm root zone before initiating irrigation.",
                "Opt for morning or evening drip cycles to minimize evaporative losses.",
                "Plan next irrigation cycle within 2 to 3 days depending on crop growth stage."
            ]
        elif deficit_48h > 10.0 or cur_vpd > 2.0:
            risk_level = "CRITICAL"
            advisory_hl = "High atmospheric moisture deficit with zero expected rainfall."
            advisory_body = (
                f"No meaningful rain is forecast over the next 72 hours, while atmospheric water demand will draw {et0_72h} mm from the soil. "
                f"Current VPD is elevated at {cur_vpd} kPa. Crop transpiration stress will peak during afternoon hours."
            )
            field_actions = [
                "Schedule priority irrigation cycles to maintain root-zone soil moisture above refill threshold.",
                "Irrigate during early morning (05:00–08:30) or late evening to maximize infiltration efficiency.",
                "Apply organic mulching or avoid mid-day mechanical field operations that accelerate moisture loss."
            ]
        else:
            risk_level = "HIGH"
            advisory_hl = "Elevated evaporative demand outpaces forecast rainfall."
            advisory_body = (
                f"Atmospheric evaporative demand ({et0_48h} mm in 48h) exceeds forecasted precipitation ({rain_48h} mm), resulting in a net moisture deficit of {deficit_48h} mm. "
                "Upcoming dry window spans several consecutive days."
            )
            field_actions = [
                "Schedule supplementary irrigation to compensate for the 48h moisture deficit.",
                "Prioritize flowering/grain-filling stages most vulnerable to water stress.",
                "Keep irrigation intervals steady to prevent stomatal shock."
            ]

        irrigation_outlook = IrrigationOutlook(
            forecast_rainfall_48h_mm=rain_48h,
            forecast_rainfall_72h_mm=rain_72h,
            forecast_et0_48h_mm=et0_48h,
            forecast_et0_72h_mm=et0_72h,
            net_atmospheric_deficit_48h_mm=deficit_48h,
            net_atmospheric_deficit_72h_mm=deficit_72h,
            rain_probability_max_48h=rain_prob_48h,
            upcoming_dry_days_count=dry_days,
            risk_level=risk_level,
            advisory_headline=advisory_hl,
            advisory_body=advisory_body,
            field_actions=field_actions,
        )

        # 7. Weather Alerts Engine (Deterministic thresholds on real data)
        alerts: List[WeatherAlert] = []

        # Check Heavy Rain in next 24h
        next_24h_precip = sum(h.precipitation for h in hourly_items[:24])
        max_hourly_rain = max((h.rain + h.showers for h in hourly_items[:24]), default=0.0)
        if max_hourly_rain >= 15.0 or next_24h_precip >= 35.0:
            alerts.append(
                WeatherAlert(
                    id="alert_heavy_rain",
                    severity="warning",
                    category="rainfall",
                    title="Heavy Rainfall Alert",
                    message=f"Intense rainfall forecast with up to {max_hourly_rain} mm/h and {round(next_24h_precip, 1)} mm accumulated over the next 24 hours.",
                    recommendation="Ensure field bund drainage gates are open to prevent root-zone submergence and soil erosion.",
                    time_window="Next 24 Hours",
                )
            )
        elif next_24h_precip >= 15.0:
            alerts.append(
                WeatherAlert(
                    id="alert_mod_rain",
                    severity="caution",
                    category="rainfall",
                    title="Moderate Rainfall Expected",
                    message=f"Accumulated rainfall of approximately {round(next_24h_precip, 1)} mm expected within the next 24 hours.",
                    recommendation="Postpone pesticide spraying and fertilizer application until foliage dries.",
                    time_window="Next 24 Hours",
                )
            )

        # Check Thunderstorm in next 24h
        has_storm = any(h.weather_code in [95, 96, 99] for h in hourly_items[:24])
        if has_storm:
            alerts.append(
                WeatherAlert(
                    id="alert_thunderstorm",
                    severity="warning",
                    category="storm",
                    title="Thunderstorm & Convective Activity",
                    message="Thunderstorm cells with gusty winds and lightning activity are forecast in the local area.",
                    recommendation="Secure loose agricultural equipment and pause all open field operations during storm passage.",
                    time_window="Next 12–24 Hours",
                )
            )

        # Check High Winds / Gusts
        max_gust = max((h.wind_gusts for h in hourly_items[:24]), default=cur_wgust)
        max_wind = max((h.wind_speed for h in hourly_items[:24]), default=cur_wspeed)
        if max_gust >= 45.0 or max_wind >= 32.0:
            alerts.append(
                WeatherAlert(
                    id="alert_high_wind",
                    severity="caution",
                    category="wind",
                    title="Strong Wind Gusts Forecast",
                    message=f"Wind gusts up to {round(max_gust, 1)} km/h forecast. Risk of crop lodging in tall crops (paddy, maize, sugarcane).",
                    recommendation="Avoid spray treatments (drift risk) and verify stake supports for vulnerable orchard trees or tall crops.",
                    time_window="Next 24 Hours",
                )
            )

        # Check Extreme Heat / Frost
        max_temp_24h = max((h.temperature for h in hourly_items[:24]), default=cur_temp)
        min_temp_24h = min((h.temperature for h in hourly_items[:24]), default=cur_temp)
        if max_temp_24h >= 40.0:
            alerts.append(
                WeatherAlert(
                    id="alert_extreme_heat",
                    severity="warning",
                    category="temperature",
                    title="High Temperature Stress (Heat Wave)",
                    message=f"Peak ambient temperature will reach {round(max_temp_24h, 1)}°C, exceeding optimal physiological thresholds.",
                    recommendation="Conduct light canopy misting or early morning irrigation to reduce crop canopy temperature.",
                    time_window="Today's Peak Hours (12:00–16:00)",
                )
            )
        elif min_temp_24h <= 4.0:
            alerts.append(
                WeatherAlert(
                    id="alert_frost",
                    severity="warning",
                    category="temperature",
                    title="Cold Wave / Frost Risk",
                    message=f"Night/early morning temperatures are projected to drop to {round(min_temp_24h, 1)}°C with potential ground frost.",
                    recommendation="Apply light evening irrigation or smudge smoke cover to elevate ground temperature.",
                    time_window="Overnight / Early Dawn",
                )
            )

        # Check VPD / Dryness
        if cur_vpd >= 2.0:
            alerts.append(
                WeatherAlert(
                    id="alert_vpd_high",
                    severity="advisory",
                    category="vpd",
                    title="Elevated Atmospheric Vapor Pressure Deficit",
                    message=f"Atmospheric VPD is currently high at {cur_vpd} kPa, accelerating crop transpirational water demand.",
                    recommendation="Check soil moisture to ensure crop stomata do not permanently close during midday.",
                    time_window="Current & Afternoon",
                )
            )
        elif cur_rh >= 88.0 and cur_temp >= 22.0:
            alerts.append(
                WeatherAlert(
                    id="alert_humidity_fungal",
                    severity="advisory",
                    category="humidity",
                    title="High Humidity & Foliar Fungal Risk",
                    message=f"Sustained high humidity ({cur_rh}%) with warm temperatures creates favorable conditions for foliar pathogens.",
                    recommendation="Scout crop canopies for early signs of blast, blight, or powdery mildew.",
                    time_window="Current Atmospheric Window",
                )
            )

        # Check Extended Dry Window
        if dry_days >= 6 and rain_72h < 1.0:
            alerts.append(
                WeatherAlert(
                    id="alert_extended_dry",
                    severity="advisory",
                    category="drought",
                    title="Extended Dry Weather Window",
                    message=f"6+ consecutive dry days forecast with total rainfall under 1 mm across the next 7 days.",
                    recommendation="Favorable window for mechanized harvesting, weeding, and soil tillage operations.",
                    time_window="Next 7 Days",
                )
            )

        # 8. Solar & Daylight
        sunrise_str = daily_items[0].sunrise if daily_items else "06:00"
        sunset_str = daily_items[0].sunset if daily_items else "18:30"
        cur_uv = float(hourly_raw.get("uv_index", [0.0])[cur_h_idx] or 0.0)
        max_uv = daily_items[0].uv_index_max if daily_items else cur_uv
        rad_direct = float(hourly_raw.get("direct_radiation", [0.0])[cur_h_idx] or 0.0)
        rad_sw = float(hourly_raw.get("shortwave_radiation", [0.0])[cur_h_idx] or 0.0)
        rad_diff = float(hourly_raw.get("diffuse_radiation", [0.0])[cur_h_idx] or 0.0)

        # Calculate sun position percentage (0 = sunrise, 50 = noon, 100 = sunset)
        try:
            sunrise_dt = datetime.fromisoformat(sunrise_str)
            sunset_dt = datetime.fromisoformat(sunset_str)
            total_daylight_sec = (sunset_dt - sunrise_dt).total_seconds()
            elapsed_sec = (now_dt.replace(tzinfo=None) - sunrise_dt).total_seconds()
            if total_daylight_sec > 0:
                sun_pos_pct = round(max(0.0, min(100.0, (elapsed_sec / total_daylight_sec) * 100)), 1)
            else:
                sun_pos_pct = 50.0
        except Exception:
            sun_pos_pct = 50.0 if cur_is_day else 0.0

        solar = SolarConditions(
            sunrise=sunrise_str.split("T")[1][:5] if "T" in sunrise_str else sunrise_str,
            sunset=sunset_str.split("T")[1][:5] if "T" in sunset_str else sunset_str,
            daylight_duration_hours=daily_items[0].daylight_duration_hours if daily_items else 12.0,
            sunshine_duration_hours=daily_items[0].sunshine_duration_hours if daily_items else 8.0,
            uv_index_current=round(cur_uv, 1),
            uv_index_max=round(max_uv, 1),
            direct_radiation_wm2=round(rad_direct, 1),
            shortwave_radiation_wm2=round(rad_sw, 1),
            diffuse_radiation_wm2=round(rad_diff, 1),
            sun_position_percent=sun_pos_pct,
            is_day=cur_is_day,
        )

        # 9. Wind Conditions
        wind_trend = []
        for h in hourly_items[:24]:
            wind_trend.append({
                "time": h.hour_label,
                "speed": h.wind_speed,
                "gusts": h.wind_gusts,
                "direction": h.wind_direction,
            })

        wind = WindConditions(
            speed_kmh=cur_wspeed,
            direction_degrees=int(cur_wdir),
            cardinal_direction=_get_cardinal_direction(cur_wdir),
            gusts_kmh=cur_wgust,
            wind_scale_description=_get_beaufort_description(cur_wspeed),
            hourly_trend=wind_trend,
        )

        # 10. Atmospheric Conditions
        visibility_val = hourly_items[0].visibility_km if hourly_items and hourly_items[0].visibility_km else 10.0
        atmospheric = AtmosphericConditions(
            relative_humidity_percent=cur_rh,
            dew_point_c=cur_dew or round(cur_temp - ((100 - cur_rh) / 5), 1),
            apparent_temperature_c=cur_atemp,
            surface_pressure_hpa=round(float(current_raw.get("surface_pressure", 1000.0)), 1),
            sea_level_pressure_hpa=round(float(current_raw.get("pressure_msl", 1013.0)), 1),
            cloud_cover_percent=int(current_raw.get("cloud_cover", 20)),
            visibility_km=round(visibility_val, 1),
            vpd_kpa=cur_vpd,
            vpd_status=vpd_status,
        )

        # 11. Day Timeline Periods (Morning, Afternoon, Evening, Night)
        timeline = WeatherService._build_timeline(hourly_raw, d_times[0] if d_times else "")

        # 12. Today Summary Generator (Deterministic Natural Language)
        today_summary = WeatherService._generate_natural_summary(
            current=current,
            today_daily=daily_items[0] if daily_items else None,
            et0_today=et0_today,
            cur_vpd=cur_vpd,
            alerts_count=len(alerts),
        )

        return WeatherResponse(
            location=location,
            metadata=metadata,
            today_summary=today_summary,
            current=current,
            timeline=timeline,
            hourly=hourly_items,
            daily=daily_items,
            agricultural=agricultural,
            irrigation_outlook=irrigation_outlook,
            alerts=alerts,
            solar=solar,
            wind=wind,
            atmospheric=atmospheric,
        )

    @staticmethod
    def _build_timeline(hourly_raw: Dict[str, Any], date_str: str) -> List[TimelinePeriod]:
        """
        Extracts representative conditions for Morning (06-12), Afternoon (12-17),
        Evening (17-21), and Night (21-06) for the current forecast date.
        """
        times = hourly_raw.get("time", [])
        temps = hourly_raw.get("temperature_2m", [])
        codes = hourly_raw.get("weather_code", [])
        pprob = hourly_raw.get("precipitation_probability", [])
        rain = hourly_raw.get("rain", [])
        rhs = hourly_raw.get("relative_humidity_2m", [])
        winds = hourly_raw.get("wind_speed_10m", [])

        # Time ranges
        ranges = [
            ("Morning", "06:00 – 12:00", [6, 8, 10], True),
            ("Afternoon", "12:00 – 17:00", [12, 14, 16], True),
            ("Evening", "17:00 – 21:00", [17, 19, 20], True),
            ("Night", "21:00 – 06:00", [21, 23, 2], False),
        ]

        periods: List[TimelinePeriod] = []

        for name, trange, sample_hours, is_day in ranges:
            matching_indices = []
            for idx, t in enumerate(times[:48]):
                try:
                    hr = int(t.split("T")[1][:2])
                    if hr in sample_hours:
                        matching_indices.append(idx)
                except Exception:
                    pass

            if not matching_indices:
                matching_indices = [0]

            # Averages & representative code
            avg_temp = round(sum(temps[i] for i in matching_indices if i < len(temps) and temps[i] is not None) / len(matching_indices), 1) if matching_indices else 25.0
            avg_rh = int(sum(rhs[i] for i in matching_indices if i < len(rhs) and rhs[i] is not None) / len(matching_indices)) if matching_indices else 50
            avg_wind = round(sum(winds[i] for i in matching_indices if i < len(winds) and winds[i] is not None) / len(matching_indices), 1) if matching_indices else 10.0
            max_prob = max((pprob[i] for i in matching_indices if i < len(pprob) and pprob[i] is not None), default=0)
            sum_rain = round(sum(rain[i] for i in matching_indices if i < len(rain) and rain[i] is not None), 1) if matching_indices else 0.0

            rep_code = codes[matching_indices[0]] if matching_indices and matching_indices[0] < len(codes) and codes[matching_indices[0]] is not None else 0

            periods.append(
                TimelinePeriod(
                    period=name,
                    time_range=trange,
                    temperature=avg_temp,
                    condition=_decode_wmo_code(rep_code, is_day=is_day),
                    precipitation_probability=int(max_prob),
                    rain_mm=sum_rain,
                    relative_humidity=avg_rh,
                    wind_speed=avg_wind,
                )
            )

        return periods

    @staticmethod
    def _generate_natural_summary(
        current: CurrentWeather,
        today_daily: Optional[DailyForecastItem],
        et0_today: float,
        cur_vpd: float,
        alerts_count: int,
    ) -> str:
        """
        Constructs a cohesive, natural agronomic forecast summary.
        """
        cond_text = current.condition.label.lower()
        tmax = today_daily.temp_max if today_daily else current.temperature + 4.0
        tmin = today_daily.temp_min if today_daily else current.temperature - 4.0
        rain_prob = today_daily.precipitation_probability_max if today_daily else current.precipitation_probability or 0
        rain_sum = today_daily.precipitation_sum if today_daily else 0.0

        sentences = []

        # 1. Condition & Temperature overview
        if current.temperature >= 35.0:
            sentences.append(f"Hot and {cond_text} conditions dominate today with ambient temperatures reaching a peak of {tmax}°C and cooling to {tmin}°C overnight.")
        elif current.temperature <= 16.0:
            sentences.append(f"Cool and {cond_text} weather is expected today, with temperatures ranging between {tmin}°C and {tmax}°C.")
        else:
            sentences.append(f"Pleasant and {cond_text} conditions are expected today with a high of {tmax}°C and an overnight low of {tmin}°C.")

        # 2. Precipitation outlook
        if rain_sum >= 5.0 or rain_prob >= 60:
            sentences.append(f"Rainfall probability is significant ({rain_prob}%) with approximately {rain_sum} mm of precipitation expected across the day.")
        elif rain_prob >= 25:
            sentences.append(f"A slight to moderate precipitation chance ({rain_prob}%) exists during peak convective hours.")
        else:
            sentences.append("Dry conditions with negligible rainfall probability will prevail through the daylight hours.")

        # 3. Agricultural evaporative demand & VPD
        if et0_today >= 6.0 or cur_vpd >= 1.6:
            sentences.append(f"Atmospheric moisture demand is elevated with an estimated ET₀ of {et0_today} mm/day and VPD at {cur_vpd} kPa, accelerating soil moisture depletion.")
        elif et0_today <= 3.2:
            sentences.append(f"Atmospheric evaporative demand remains low (ET₀ {et0_today} mm/day), keeping soil moisture levels relatively stable.")
        else:
            sentences.append(f"Atmospheric water demand is moderate (ET₀ {et0_today} mm/day), supporting balanced crop transpiration.")

        # 4. Wind & Alerts context
        if current.wind_speed >= 25.0:
            sentences.append(f"Fresh {current.wind_direction_cardinal} winds averaging {current.wind_speed} km/h (gusting to {current.wind_gusts} km/h) may increase crop drift during spraying.")
        elif alerts_count > 0:
            sentences.append(f"{alerts_count} active agronomic advisory alerts are in effect for this location.")

        return " ".join(sentences)
