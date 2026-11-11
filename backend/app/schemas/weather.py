from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class WeatherConditionInfo(BaseModel):
    code: int
    label: str
    description: str
    icon_type: str  # e.g. "sunny", "partly_cloudy", "cloudy", "fog", "drizzle", "rain", "heavy_rain", "thunderstorm", "snow"
    is_day: bool = True


class CurrentWeather(BaseModel):
    time: str
    temperature: float = Field(..., description="Current 2m air temperature in °C")
    apparent_temperature: float = Field(..., description="Feels like temperature in °C")
    is_day: bool
    relative_humidity: float = Field(..., description="Relative humidity in %")
    dew_point: Optional[float] = Field(None, description="Dew point in °C")
    precipitation: float = Field(0.0, description="Current precipitation rate in mm")
    rain: float = Field(0.0, description="Rain in mm")
    showers: float = Field(0.0, description="Showers in mm")
    snowfall: float = Field(0.0, description="Snowfall in cm")
    cloud_cover: int = Field(..., description="Total cloud cover in %")
    pressure_msl: float = Field(..., description="Sea level atmospheric pressure in hPa")
    surface_pressure: float = Field(..., description="Surface atmospheric pressure in hPa")
    wind_speed: float = Field(..., description="Wind speed at 10m in km/h")
    wind_direction: int = Field(..., description="Wind direction at 10m in degrees (0-360)")
    wind_direction_cardinal: str = Field("N", description="Cardinal direction (N, NE, E, SE, S, SW, W, NW)")
    wind_gusts: float = Field(0.0, description="Wind gusts at 10m in km/h")
    weather_code: int
    condition: WeatherConditionInfo
    temp_max_today: Optional[float] = None
    temp_min_today: Optional[float] = None
    precipitation_probability: Optional[int] = 0


class HourlyForecastItem(BaseModel):
    time: str
    hour_label: str
    temperature: float
    apparent_temperature: float
    relative_humidity: int
    dew_point: Optional[float] = None
    precipitation_probability: int
    precipitation: float
    rain: float
    showers: float
    snowfall: float
    weather_code: int
    condition: WeatherConditionInfo
    pressure_msl: float
    surface_pressure: float
    cloud_cover: int
    visibility_km: Optional[float] = None
    evapotranspiration: Optional[float] = None
    et0: Optional[float] = None
    vpd_kpa: Optional[float] = None
    wind_speed: float
    wind_direction: int
    wind_direction_cardinal: str
    wind_gusts: float
    uv_index: Optional[float] = None
    direct_radiation: Optional[float] = None
    shortwave_radiation: Optional[float] = None
    soil_moisture_surface: Optional[float] = None  # 0-1cm (m³/m³)
    soil_temperature_surface: Optional[float] = None  # 0cm (°C)


class DailyForecastItem(BaseModel):
    date: str
    day_name: str
    formatted_date: str
    weather_code: int
    condition: WeatherConditionInfo
    temp_max: float
    temp_min: float
    apparent_temp_max: float
    apparent_temp_min: float
    sunrise: str
    sunset: str
    daylight_duration_hours: float
    sunshine_duration_hours: float
    uv_index_max: float
    precipitation_sum: float
    rain_sum: float
    showers_sum: float
    snowfall_sum: float
    precipitation_hours: float
    precipitation_probability_max: int
    wind_speed_max: float
    wind_gusts_max: float
    wind_direction_dominant: int
    wind_direction_cardinal: str
    et0_fao_sum: Optional[float] = None
    shortwave_radiation_sum: Optional[float] = None


class SoilMoistureDepth(BaseModel):
    depth_label: str  # e.g., "0–1 cm (Surface)", "1–3 cm", "3–9 cm", "9–27 cm (Root Zone)", "27–81 cm (Deep)"
    depth_code: str
    moisture_m3m3: float  # volumetric fraction m³/m³
    moisture_percentage: float  # scaled percentage representation
    status: str  # "Saturated", "Adequate", "Moderate Deficit", "Dry"


class SoilTemperatureDepth(BaseModel):
    depth_label: str  # e.g., "0 cm (Surface)", "6 cm", "18 cm (Seed Zone)", "54 cm (Sub-Soil)"
    temperature_c: float


class AgriculturalWeather(BaseModel):
    et0_today_mm: float
    et0_weekly_total_mm: float
    et0_interpretation: str
    et0_trend: List[dict]  # [{ date: str, et0: float, rain: float }]
    soil_moisture_levels: List[SoilMoistureDepth]
    soil_temperatures: List[SoilTemperatureDepth]
    current_vpd_kpa: float
    vpd_status: str  # "Low (Fungal Risk)", "Optimal", "Moderate Stress", "High Stress", "Severe Stress"
    vpd_explanation: str
    vpd_trend: List[dict]  # [{ time: str, vpd: float }]


class IrrigationOutlook(BaseModel):
    forecast_rainfall_48h_mm: float
    forecast_rainfall_72h_mm: float
    forecast_et0_48h_mm: float
    forecast_et0_72h_mm: float
    net_atmospheric_deficit_48h_mm: float
    net_atmospheric_deficit_72h_mm: float
    rain_probability_max_48h: int
    upcoming_dry_days_count: int
    risk_level: str  # "LOW", "MODERATE", "HIGH", "CRITICAL"
    advisory_headline: str
    advisory_body: str
    field_actions: List[str]
    scientific_disclaimer: str = "Weather-based atmospheric water balance contribution to irrigation assessment. For physical sub-surface root-zone measurements, consult the Soil Moisture analysis module."


class WeatherAlert(BaseModel):
    id: str
    severity: str  # "advisory", "caution", "warning", "critical"
    category: str  # "rainfall", "temperature", "wind", "vpd", "drought", "storm"
    title: str
    message: str
    recommendation: str
    time_window: str


class SolarConditions(BaseModel):
    sunrise: str
    sunset: str
    daylight_duration_hours: float
    sunshine_duration_hours: float
    uv_index_current: float
    uv_index_max: float
    direct_radiation_wm2: float
    shortwave_radiation_wm2: float
    diffuse_radiation_wm2: float
    sun_position_percent: float  # 0 to 100% of daylight elapsed
    is_day: bool


class WindConditions(BaseModel):
    speed_kmh: float
    direction_degrees: int
    cardinal_direction: str
    gusts_kmh: float
    wind_scale_description: str  # Beaufort scale description (e.g., "Gentle Breeze", "Moderate Breeze")
    hourly_trend: List[dict]  # [{ time: str, speed: float, gusts: float, direction: int }]


class AtmosphericConditions(BaseModel):
    relative_humidity_percent: float
    dew_point_c: float
    apparent_temperature_c: float
    surface_pressure_hpa: float
    sea_level_pressure_hpa: float
    cloud_cover_percent: int
    visibility_km: float
    vpd_kpa: float
    vpd_status: str


class TimelinePeriod(BaseModel):
    period: str  # "Morning", "Afternoon", "Evening", "Night"
    time_range: str
    temperature: float
    condition: WeatherConditionInfo
    precipitation_probability: int
    rain_mm: float
    relative_humidity: int
    wind_speed: float


class ModelMetadata(BaseModel):
    provider: str = "Open-Meteo"
    primary_model: str = "ECMWF IFS HRES"
    grid_resolution: str = "≈ 9 km"
    elevation_m: Optional[float] = None
    latitude: float
    longitude: float
    timezone: str = "Asia/Kolkata"
    timezone_abbreviation: str = "IST"
    generation_time_ms: float
    cached: bool = False
    fetched_at_ist: str


class LocationContext(BaseModel):
    field_id: Optional[str] = None
    field_name: Optional[str] = None
    village: Optional[str] = None
    tehsil: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = "India"
    area_hectares: Optional[float] = None
    area_acres: Optional[float] = None
    latitude: float
    longitude: float


class WeatherResponse(BaseModel):
    location: LocationContext
    metadata: ModelMetadata
    today_summary: str
    current: CurrentWeather
    timeline: List[TimelinePeriod]
    hourly: List[HourlyForecastItem]
    daily: List[DailyForecastItem]
    agricultural: AgriculturalWeather
    irrigation_outlook: IrrigationOutlook
    alerts: List[WeatherAlert]
    solar: SolarConditions
    wind: WindConditions
    atmospheric: AtmosphericConditions
