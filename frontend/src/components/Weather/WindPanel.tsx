import React from "react";
import { Wind, Compass } from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

interface WindPanelProps {
  wind: {
    speed_kmh: number;
    direction_degrees: number;
    cardinal_direction: string;
    gusts_kmh: number;
    wind_scale_description: string;
    hourly_trend: Array<{
      time: string;
      speed: number;
      gusts: number;
      direction: number;
    }>;
  };
}

export const WindPanel: React.FC<WindPanelProps> = ({ wind }) => {
  return (
    <div className="weather-card">
      <div className="weather-card-header">
        <div className="weather-card-title-group">
          <div className="weather-card-title-icon">
            <Wind size={18} />
          </div>
          <div>
            <h3 className="weather-card-title">Wind Intelligence</h3>
            <span className="weather-card-subtitle">Vector velocity & spray drift risk</span>
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "130px 1fr", gap: "16px", alignItems: "center", marginBottom: "16px" }}>
        {/* Animated Compass Rose */}
        <div className="compass-wrapper">
          <span className="compass-cardinal compass-n">N</span>
          <span className="compass-cardinal compass-s">S</span>
          <span className="compass-cardinal compass-e">E</span>
          <span className="compass-cardinal compass-w">W</span>

          <div
            className="compass-arrow-needle"
            style={{ transform: `rotate(${wind.direction_degrees}deg)` }}
          >
            <div className="needle-north" />
            <div className="needle-south" />
            <div className="needle-center-dot" />
          </div>
        </div>

        {/* Wind Statistics */}
        <div>
          <div style={{ fontSize: "1.9rem", fontWeight: 800, color: "#1e293b" }}>
            {wind.speed_kmh} <small style={{ fontSize: "1rem", color: "#64748b", fontWeight: 500 }}>km/h</small>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "4px" }}>
            <span className="location-chip" style={{ background: "#f1f5f9", color: "#334155" }}>
              <Compass size={13} />
              {wind.cardinal_direction} ({wind.direction_degrees}°)
            </span>
            <span style={{ fontSize: "0.82rem", fontWeight: 600, color: "#475569" }}>
              {wind.wind_scale_description}
            </span>
          </div>

          <div style={{ fontSize: "0.82rem", color: "#64748b", marginTop: "6px" }}>
            Peak Gusts: <strong style={{ color: "#0f172a" }}>{wind.gusts_kmh} km/h</strong>
          </div>
        </div>
      </div>

      {/* 24h Hourly Wind Trend Chart */}
      <span style={{ fontSize: "0.74rem", fontWeight: 700, color: "#64748b", textTransform: "uppercase" }}>
        24-Hour Wind Velocity & Gusts
      </span>

      <div style={{ height: 120, width: "100%", marginTop: "6px" }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={wind.hourly_trend} margin={{ top: 5, right: 5, left: -25, bottom: 0 }}>
            <defs>
              <linearGradient id="windSpeedGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.35} />
                <stop offset="95%" stopColor="#10b981" stopOpacity={0.0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
            <XAxis dataKey="time" tick={{ fontSize: 10, fill: "#64748b" }} interval={3} />
            <YAxis tick={{ fontSize: 10, fill: "#64748b" }} unit="k" />
            <Tooltip
              formatter={(val: any, name: any) => [`${val} km/h`, name === "speed" ? "Wind Speed" : "Gusts"]}
            />
            <Area
              type="monotone"
              dataKey="speed"
              stroke="#059669"
              strokeWidth={2}
              fillOpacity={1}
              fill="url(#windSpeedGrad)"
              name="speed"
            />
            <Area
              type="monotone"
              dataKey="gusts"
              stroke="#cbd5e1"
              strokeWidth={1.5}
              strokeDasharray="3 3"
              fill="none"
              name="gusts"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default WindPanel;
