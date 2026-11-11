import React, { useState, useEffect, useCallback } from "react";
import {
  Sparkles,
  AlertOctagon,
  RefreshCw,
  Cpu,
} from "lucide-react";
import ApiService from "../../services/api";
import { useFieldContext } from "../../layouts/DashboardLayout";
import WeatherBackground from "../../components/Weather/WeatherBackground";
import WeatherHeader from "../../components/Weather/WeatherHeader";
import CurrentWeatherHero from "../../components/Weather/CurrentWeatherHero";
import WeatherTimelinePanel from "../../components/Weather/WeatherTimelinePanel";
import HourlyForecastPanel from "../../components/Weather/HourlyForecastPanel";
import DailyForecastPanel from "../../components/Weather/DailyForecastPanel";
import AgriculturalWeatherPanel from "../../components/Weather/AgriculturalWeatherPanel";
import IrrigationOutlookPanel from "../../components/Weather/IrrigationOutlookPanel";
import WindPanel from "../../components/Weather/WindPanel";
import SolarPanel from "../../components/Weather/SolarPanel";
import AtmosphericPanel from "../../components/Weather/AtmosphericPanel";
import WeatherAlertsPanel from "../../components/Weather/WeatherAlertsPanel";
import WeatherSkeleton from "../../components/Weather/WeatherSkeleton";
import "./WeatherPage.css";

// Default coordinates (Ludhiana / Punjab agricultural center) if no field selected yet
const DEFAULT_LAT = 30.9010;
const DEFAULT_LON = 75.8573;

export const WeatherPage: React.FC = () => {
  const { activeFieldId, setActiveFieldId, selectedFieldData, setSelectedFieldData } = useFieldContext();

  const [forecast, setForecast] = useState<any | null>(null);
  const [availableFields, setAvailableFields] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Load user saved fields for quick switching
  useEffect(() => {
    ApiService.listFields()
      .then((fields) => {
        setAvailableFields(fields || []);
      })
      .catch((err) => {
        console.warn("Could not fetch fields list for weather selector:", err);
      });
  }, []);

  // Determine current coordinates
  const currentLat = selectedFieldData?.latitude || DEFAULT_LAT;
  const currentLon = selectedFieldData?.longitude || DEFAULT_LON;
  const currentFieldId = selectedFieldData?.field_id || activeFieldId || null;

  const fetchForecast = useCallback(
    async (forceRefresh: boolean = false) => {
      if (forceRefresh) {
        setIsRefreshing(true);
      } else {
        setIsLoading(true);
      }
      setError(null);

      try {
        const data = await ApiService.getWeatherForecast(
          currentLat,
          currentLon,
          forceRefresh,
          currentFieldId
        );
        setForecast(data);
      } catch (err: any) {
        setError(err.message || "Failed to load weather forecast. Please check your connection.");
      } finally {
        setIsLoading(false);
        setIsRefreshing(false);
      }
    },
    [currentLat, currentLon, currentFieldId]
  );

  useEffect(() => {
    fetchForecast(false);
  }, [fetchForecast]);

  const handleSelectField = (fieldId: string) => {
    const found = availableFields.find((f) => f.field_id === fieldId);
    if (found) {
      setActiveFieldId(found.field_id);
      setSelectedFieldData(found);
    }
  };

  if (isLoading && !forecast) {
    return (
      <div className="weather-page-container">
        <WeatherSkeleton />
      </div>
    );
  }

  if (error && !forecast) {
    return (
      <div className="weather-page-container">
        <div className="weather-card" style={{ textAlign: "center", padding: "48px 24px" }}>
          <AlertOctagon size={48} color="#ef4444" style={{ margin: "0 auto 16px" }} />
          <h2 style={{ fontSize: "1.3rem", color: "#1e293b", marginBottom: "8px" }}>
            Weather Service Temporarily Unavailable
          </h2>
          <p style={{ color: "#64748b", maxWidth: "480px", margin: "0 auto 20px" }}>
            {error}
          </p>
          <button
            onClick={() => fetchForecast(true)}
            className="weather-refresh-btn"
            style={{ margin: "0 auto" }}
          >
            <RefreshCw size={16} />
            <span>Retry Connection</span>
          </button>
        </div>
      </div>
    );
  }

  if (!forecast) return null;

  return (
    <div className="weather-page-container">
      {/* Reactive Ambient Background */}
      <WeatherBackground
        iconType={forecast.current.condition.icon_type}
        isDay={forecast.current.is_day}
      />

      {/* Top Header & Field Selector */}
      <WeatherHeader
        location={forecast.location}
        metadata={forecast.metadata}
        availableFields={availableFields}
        onSelectField={handleSelectField}
        onRefresh={() => fetchForecast(true)}
        isRefreshing={isRefreshing}
      />

      {/* Natural Language Agronomic Summary */}
      <div className="weather-summary-banner">
        <div className="summary-icon-badge">
          <Sparkles size={20} />
        </div>
        <div style={{ flex: 1 }}>
          <strong style={{ color: "#14532d", marginRight: "6px" }}>Today's Agronomic Weather Summary:</strong>
          <span>{forecast.today_summary}</span>
        </div>
      </div>

      {/* Weather Alerts (if any) */}
      {forecast.alerts && forecast.alerts.length > 0 && (
        <WeatherAlertsPanel alerts={forecast.alerts} />
      )}

      {/* Hero Section: Live Atmosphere + Day Progression */}
      <div className="weather-hero-grid">
        <CurrentWeatherHero current={forecast.current} />
        <WeatherTimelinePanel timeline={forecast.timeline} />
      </div>

      {/* Hourly Forecast (24 Hours) + Charts */}
      <HourlyForecastPanel hourly={forecast.hourly} />

      {/* 10-Day Medium-Range Outlook */}
      <DailyForecastPanel daily={forecast.daily} />

      {/* Agricultural Weather Intelligence (ET0, Multi-depth Soil, VPD) */}
      <AgriculturalWeatherPanel agricultural={forecast.agricultural} />

      {/* Irrigation Weather Outlook */}
      <IrrigationOutlookPanel outlook={forecast.irrigation_outlook} />

      {/* Wind & Solar Dynamics Grid */}
      <div className="wind-solar-grid">
        <WindPanel wind={forecast.wind} />
        <SolarPanel solar={forecast.solar} />
      </div>

      {/* Atmospheric & Boundary Layer Details */}
      <AtmosphericPanel atmospheric={forecast.atmospheric} />

      {/* Transparency & Data Source Footer Card */}
      <div
        className="weather-card"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "12px",
          padding: "14px 20px",
          background: "rgba(255, 255, 255, 0.7)",
          fontSize: "0.8rem",
          color: "#64748b",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <Cpu size={16} color="#15803d" />
          <span>
            Forecast Engine: <strong>Open-Meteo API</strong> • High-Resolution Global Model: <strong>ECMWF IFS HRES (0.1° / 0.25°)</strong>
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <span>Grid Coordinates: {forecast.location.latitude.toFixed(4)}°N, {forecast.location.longitude.toFixed(4)}°E</span>
          <span>Timezone: {forecast.metadata.timezone_abbreviation} (UTC+05:30)</span>
        </div>
      </div>
    </div>
  );
};

export default WeatherPage;
