import React from "react";
import {
  Gauge,
  Droplets,
  Cloud,
  Eye,
  Activity,
  Thermometer,
} from "lucide-react";

interface AtmosphericPanelProps {
  atmospheric: {
    relative_humidity_percent: number;
    dew_point_c: number;
    apparent_temperature_c: number;
    surface_pressure_hpa: number;
    sea_level_pressure_hpa: number;
    cloud_cover_percent: number;
    visibility_km: number;
    vpd_kpa: number;
    vpd_status: string;
  };
}

export const AtmosphericPanel: React.FC<AtmosphericPanelProps> = ({ atmospheric }) => {
  return (
    <div className="weather-card">
      <div className="weather-card-header">
        <div className="weather-card-title-group">
          <div className="weather-card-title-icon">
            <Gauge size={18} />
          </div>
          <div>
            <h3 className="weather-card-title">Atmospheric & Humidity Parameters</h3>
            <span className="weather-card-subtitle">Boundary layer thermodynamics & barometric status</span>
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: "12px" }}>
        <div style={{ background: "#f8fafc", padding: "12px", borderRadius: "10px", border: "1px solid #e2e8f0" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.76rem", color: "#64748b", fontWeight: 600 }}>
            <Droplets size={14} color="#3b82f6" /> Relative Humidity
          </div>
          <div style={{ fontSize: "1.3rem", fontWeight: 800, color: "#1e293b", marginTop: "4px" }}>
            {atmospheric.relative_humidity_percent}%
          </div>
        </div>

        <div style={{ background: "#f8fafc", padding: "12px", borderRadius: "10px", border: "1px solid #e2e8f0" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.76rem", color: "#64748b", fontWeight: 600 }}>
            <Thermometer size={14} color="#06b6d4" /> Dew Point
          </div>
          <div style={{ fontSize: "1.3rem", fontWeight: 800, color: "#1e293b", marginTop: "4px" }}>
            {atmospheric.dew_point_c}°C
          </div>
        </div>

        <div style={{ background: "#f8fafc", padding: "12px", borderRadius: "10px", border: "1px solid #e2e8f0" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.76rem", color: "#64748b", fontWeight: 600 }}>
            <Gauge size={14} color="#f59e0b" /> Sea Level Pressure
          </div>
          <div style={{ fontSize: "1.3rem", fontWeight: 800, color: "#1e293b", marginTop: "4px" }}>
            {atmospheric.sea_level_pressure_hpa} <small style={{ fontSize: "0.7rem", color: "#64748b" }}>hPa</small>
          </div>
        </div>

        <div style={{ background: "#f8fafc", padding: "12px", borderRadius: "10px", border: "1px solid #e2e8f0" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.76rem", color: "#64748b", fontWeight: 600 }}>
            <Cloud size={14} color="#64748b" /> Cloud Cover
          </div>
          <div style={{ fontSize: "1.3rem", fontWeight: 800, color: "#1e293b", marginTop: "4px" }}>
            {atmospheric.cloud_cover_percent}%
          </div>
        </div>

        <div style={{ background: "#f8fafc", padding: "12px", borderRadius: "10px", border: "1px solid #e2e8f0" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.76rem", color: "#64748b", fontWeight: 600 }}>
            <Eye size={14} color="#10b981" /> Visibility
          </div>
          <div style={{ fontSize: "1.3rem", fontWeight: 800, color: "#1e293b", marginTop: "4px" }}>
            {atmospheric.visibility_km} <small style={{ fontSize: "0.7rem", color: "#64748b" }}>km</small>
          </div>
        </div>

        <div style={{ background: "#f8fafc", padding: "12px", borderRadius: "10px", border: "1px solid #e2e8f0" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.76rem", color: "#64748b", fontWeight: 600 }}>
            <Activity size={14} color="#8b5cf6" /> Vapor Pressure Deficit
          </div>
          <div style={{ fontSize: "1.3rem", fontWeight: 800, color: "#1e293b", marginTop: "4px" }}>
            {atmospheric.vpd_kpa} <small style={{ fontSize: "0.7rem", color: "#64748b" }}>kPa</small>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AtmosphericPanel;
