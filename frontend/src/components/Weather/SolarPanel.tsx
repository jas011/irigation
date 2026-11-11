import React from "react";
import {
  Sun,
  Sunrise,
  Sunset,
} from "lucide-react";

interface SolarPanelProps {
  solar: {
    sunrise: string;
    sunset: string;
    daylight_duration_hours: number;
    sunshine_duration_hours: number;
    uv_index_current: number;
    uv_index_max: number;
    direct_radiation_wm2: number;
    shortwave_radiation_wm2: number;
    diffuse_radiation_wm2: number;
    sun_position_percent: number;
    is_day: boolean;
  };
}

export const SolarPanel: React.FC<SolarPanelProps> = ({ solar }) => {
  // Compute marker position on arc
  const markerX = 10 + (solar.sun_position_percent * 0.8);
  // Parabola height y = 4 * h * x * (1 - x)
  const normX = Math.max(0, Math.min(1, solar.sun_position_percent / 100));
  const markerY = 80 - Math.sin(normX * Math.PI) * 60;

  return (
    <div className="weather-card">
      <div className="weather-card-header">
        <div className="weather-card-title-group">
          <div className="weather-card-title-icon">
            <Sun size={18} />
          </div>
          <div>
            <h3 className="weather-card-title">Solar & Daylight Dynamics</h3>
            <span className="weather-card-subtitle">Photoperiod, Irradiance & UV Radiation</span>
          </div>
        </div>

        <span
          className="location-chip"
          style={{
            background: solar.uv_index_max >= 8 ? "#fee2e2" : "#fef9c3",
            color: solar.uv_index_max >= 8 ? "#b91c1c" : "#854d0e",
          }}
        >
          UV Max: {solar.uv_index_max}
        </span>
      </div>

      {/* Sun Arc Timeline */}
      <div className="sun-arc-container">
        <div className="sun-arc-path" />

        {solar.is_day && (
          <div
            className="sun-arc-marker"
            style={{
              left: `${markerX}%`,
              top: `${markerY}px`,
            }}
          />
        )}

        <div style={{ position: "absolute", bottom: "4px", left: "10%", display: "flex", alignItems: "center", gap: "4px", fontSize: "0.8rem", fontWeight: 700, color: "#d97706" }}>
          <Sunrise size={15} /> {solar.sunrise}
        </div>

        <div style={{ position: "absolute", bottom: "4px", right: "10%", display: "flex", alignItems: "center", gap: "4px", fontSize: "0.8rem", fontWeight: 700, color: "#ea580c" }}>
          <Sunset size={15} /> {solar.sunset}
        </div>
      </div>

      {/* Solar Metrics Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))", gap: "10px", marginTop: "10px" }}>
        <div style={{ background: "#f8fafc", padding: "10px", borderRadius: "10px", border: "1px solid #e2e8f0" }}>
          <span style={{ fontSize: "0.72rem", color: "#64748b", fontWeight: 600, display: "block" }}>
            Daylight Duration
          </span>
          <span style={{ fontSize: "1.1rem", fontWeight: 700, color: "#1e293b" }}>
            {solar.daylight_duration_hours}h
          </span>
        </div>

        <div style={{ background: "#f8fafc", padding: "10px", borderRadius: "10px", border: "1px solid #e2e8f0" }}>
          <span style={{ fontSize: "0.72rem", color: "#64748b", fontWeight: 600, display: "block" }}>
            Sunshine Hours
          </span>
          <span style={{ fontSize: "1.1rem", fontWeight: 700, color: "#15803d" }}>
            {solar.sunshine_duration_hours}h
          </span>
        </div>

        <div style={{ background: "#f8fafc", padding: "10px", borderRadius: "10px", border: "1px solid #e2e8f0" }}>
          <span style={{ fontSize: "0.72rem", color: "#64748b", fontWeight: 600, display: "block" }}>
            Shortwave Radiation
          </span>
          <span style={{ fontSize: "1.1rem", fontWeight: 700, color: "#0f172a" }}>
            {solar.shortwave_radiation_wm2} <small style={{ fontSize: "0.7rem", color: "#64748b" }}>W/m²</small>
          </span>
        </div>

        <div style={{ background: "#f8fafc", padding: "10px", borderRadius: "10px", border: "1px solid #e2e8f0" }}>
          <span style={{ fontSize: "0.72rem", color: "#64748b", fontWeight: 600, display: "block" }}>
            Direct Irradiance
          </span>
          <span style={{ fontSize: "1.1rem", fontWeight: 700, color: "#d97706" }}>
            {solar.direct_radiation_wm2} <small style={{ fontSize: "0.7rem", color: "#64748b" }}>W/m²</small>
          </span>
        </div>
      </div>
    </div>
  );
};

export default SolarPanel;
