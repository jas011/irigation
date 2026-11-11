import React from "react";
import {
  Droplets,
  Wind,
  CloudRain,
  Gauge,
  Thermometer,
  Cloud,
} from "lucide-react";
import WeatherIcon from "./WeatherIcon";

interface CurrentWeatherHeroProps {
  current: {
    temperature: number;
    apparent_temperature: number;
    is_day: boolean;
    relative_humidity: number;
    dew_point?: number | null;
    precipitation: number;
    rain: number;
    showers: number;
    cloud_cover: number;
    pressure_msl: number;
    surface_pressure: number;
    wind_speed: number;
    wind_direction_cardinal: string;
    wind_gusts: number;
    condition: {
      label: string;
      description: string;
      icon_type: string;
    };
    temp_max_today?: number | null;
    temp_min_today?: number | null;
    precipitation_probability?: number | null;
  };
}

export const CurrentWeatherHero: React.FC<CurrentWeatherHeroProps> = ({ current }) => {
  return (
    <div className="weather-card hero-weather-card">
      <div>
        <div className="weather-card-header" style={{ marginBottom: "10px" }}>
          <div className="weather-card-title-group">
            <div className="weather-card-title-icon">
              <Thermometer size={18} />
            </div>
            <div>
              <h3 className="weather-card-title">Live Field Atmosphere</h3>
              <span className="weather-card-subtitle">{current.condition.description}</span>
            </div>
          </div>
          <span className="location-chip" style={{ background: "rgba(34, 197, 94, 0.1)" }}>
            High: {current.temp_max_today ?? "--"}°C • Low: {current.temp_min_today ?? "--"}°C
          </span>
        </div>

        {/* Hero Main Temperature & Condition Row */}
        <div className="hero-main-row">
          <div>
            <div className="hero-temp-group">
              <span className="hero-temp-large">{current.temperature}</span>
              <span className="hero-temp-unit">°C</span>
            </div>
            <div className="hero-feels-like">
              Feels like <strong>{current.apparent_temperature}°C</strong>
            </div>
            <div className="hero-condition-badge">
              {current.condition.label}
            </div>
          </div>

          <div className="hero-icon-container">
            <WeatherIcon
              iconType={current.condition.icon_type}
              isDay={current.is_day}
              size={64}
            />
          </div>
        </div>
      </div>

      {/* Metrics Strip */}
      <div className="hero-metrics-strip">
        <div className="metric-strip-item">
          <span className="metric-strip-label">
            <Droplets size={13} color="#3b82f6" /> Humidity
          </span>
          <span className="metric-strip-value">{current.relative_humidity}%</span>
        </div>

        <div className="metric-strip-item">
          <span className="metric-strip-label">
            <Wind size={13} color="#10b981" /> Wind
          </span>
          <span className="metric-strip-value">
            {current.wind_speed} <small style={{ fontSize: "0.75rem", color: "#64748b" }}>km/h ({current.wind_direction_cardinal})</small>
          </span>
        </div>

        <div className="metric-strip-item">
          <span className="metric-strip-label">
            <CloudRain size={13} color="#6366f1" /> Rain Chance
          </span>
          <span className="metric-strip-value">{current.precipitation_probability ?? 0}%</span>
        </div>

        <div className="metric-strip-item">
          <span className="metric-strip-label">
            <Gauge size={13} color="#eab308" /> Pressure
          </span>
          <span className="metric-strip-value">{current.pressure_msl} <small style={{ fontSize: "0.7rem", color: "#64748b" }}>hPa</small></span>
        </div>

        <div className="metric-strip-item">
          <span className="metric-strip-label">
            <Cloud size={13} color="#64748b" /> Cloud Cover
          </span>
          <span className="metric-strip-value">{current.cloud_cover}%</span>
        </div>
      </div>
    </div>
  );
};

export default CurrentWeatherHero;
