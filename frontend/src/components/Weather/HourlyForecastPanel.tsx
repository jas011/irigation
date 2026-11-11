import React, { useState } from "react";
import {
  Clock,
  Thermometer,
  CloudRain,
  Droplets,
  Wind,
} from "lucide-react";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import WeatherIcon from "./WeatherIcon";

interface HourlyItem {
  time: string;
  hour_label: string;
  temperature: number;
  apparent_temperature: number;
  relative_humidity: number;
  precipitation_probability: number;
  precipitation: number;
  rain: number;
  showers: number;
  wind_speed: number;
  wind_direction_cardinal: string;
  cloud_cover: number;
  condition: {
    label: string;
    description: string;
    icon_type: string;
    is_day: boolean;
  };
}

interface HourlyForecastPanelProps {
  hourly: HourlyItem[];
}

export const HourlyForecastPanel: React.FC<HourlyForecastPanelProps> = ({ hourly }) => {
  const [activeTab, setActiveTab] = useState<"temp" | "rain" | "humidity" | "wind">("temp");

  // Format data for recharts (first 24 hours)
  const chartData = hourly.slice(0, 24).map((h) => ({
    time: h.hour_label,
    temp: h.temperature,
    feelsLike: h.apparent_temperature,
    rainProb: h.precipitation_probability,
    rainMm: h.precipitation,
    humidity: h.relative_humidity,
    wind: h.wind_speed,
    condition: h.condition.label,
  }));

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div
          style={{
            background: "rgba(15, 23, 42, 0.92)",
            color: "#ffffff",
            padding: "8px 12px",
            borderRadius: "8px",
            fontSize: "0.8rem",
            boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
          }}
        >
          <div style={{ fontWeight: 700, marginBottom: "4px", color: "#4ade80" }}>
            {label} — {data.condition}
          </div>
          {activeTab === "temp" && (
            <>
              <div>Temperature: <strong>{data.temp}°C</strong></div>
              <div>Feels Like: <strong>{data.feelsLike}°C</strong></div>
            </>
          )}
          {activeTab === "rain" && (
            <>
              <div>Rain Probability: <strong>{data.rainProb}%</strong></div>
              <div>Precipitation: <strong>{data.rainMm} mm</strong></div>
            </>
          )}
          {activeTab === "humidity" && (
            <div>Relative Humidity: <strong>{data.humidity}%</strong></div>
          )}
          {activeTab === "wind" && (
            <div>Wind Speed: <strong>{data.wind} km/h</strong></div>
          )}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="weather-card">
      <div className="hourly-controls-bar">
        <div className="weather-card-title-group">
          <div className="weather-card-title-icon">
            <Clock size={18} />
          </div>
          <div>
            <h3 className="weather-card-title">Hourly Forecast (Next 24 Hours)</h3>
            <span className="weather-card-subtitle">Detailed atmospheric progression</span>
          </div>
        </div>

        {/* Metric Selector Tabs */}
        <div className="hourly-tab-switcher">
          <button
            className={`hourly-tab-btn ${activeTab === "temp" ? "active" : ""}`}
            onClick={() => setActiveTab("temp")}
          >
            <Thermometer size={14} /> Temp
          </button>
          <button
            className={`hourly-tab-btn ${activeTab === "rain" ? "active" : ""}`}
            onClick={() => setActiveTab("rain")}
          >
            <CloudRain size={14} /> Rain
          </button>
          <button
            className={`hourly-tab-btn ${activeTab === "humidity" ? "active" : ""}`}
            onClick={() => setActiveTab("humidity")}
          >
            <Droplets size={14} /> Humidity
          </button>
          <button
            className={`hourly-tab-btn ${activeTab === "wind" ? "active" : ""}`}
            onClick={() => setActiveTab("wind")}
          >
            <Wind size={14} /> Wind
          </button>
        </div>
      </div>

      {/* Horizontal Scrollable Hourly Cards */}
      <div className="hourly-cards-scroll-container">
        {hourly.slice(0, 24).map((h) => (
          <div key={h.time} className="hourly-card-item">
            <span className="hourly-time">{h.hour_label}</span>
            <WeatherIcon
              iconType={h.condition.icon_type}
              isDay={h.condition.is_day}
              size={24}
            />
            <span className="hourly-temp">{h.temperature}°C</span>
            <span className="hourly-rain-badge">
              <CloudRain size={11} />
              {h.precipitation_probability}%
            </span>
          </div>
        ))}
      </div>

      {/* Dynamic Metric Trend Chart */}
      <div style={{ height: 160, width: "100%", marginTop: "14px" }}>
        <ResponsiveContainer width="100%" height="100%">
          {activeTab === "rain" ? (
            <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
              <XAxis dataKey="time" tick={{ fontSize: 11, fill: "#64748b" }} interval={2} />
              <YAxis tick={{ fontSize: 11, fill: "#64748b" }} unit="%" />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="rainProb" fill="#3b82f6" radius={[4, 4, 0, 0]} name="Rain Probability" />
            </BarChart>
          ) : (
            <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="tempGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22c55e" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#22c55e" stopOpacity={0.0} />
                </linearGradient>
                <linearGradient id="humidityGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#0284c7" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#0284c7" stopOpacity={0.0} />
                </linearGradient>
                <linearGradient id="windGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
              <XAxis dataKey="time" tick={{ fontSize: 11, fill: "#64748b" }} interval={2} />
              <YAxis
                tick={{ fontSize: 11, fill: "#64748b" }}
                unit={activeTab === "temp" ? "°C" : activeTab === "humidity" ? "%" : " km/h"}
              />
              <Tooltip content={<CustomTooltip />} />
              {activeTab === "temp" && (
                <>
                  <Area
                    type="monotone"
                    dataKey="temp"
                    stroke="#16a34a"
                    strokeWidth={2.5}
                    fillOpacity={1}
                    fill="url(#tempGradient)"
                    name="Temperature"
                  />
                  <Area
                    type="monotone"
                    dataKey="feelsLike"
                    stroke="#94a3b8"
                    strokeWidth={1.5}
                    strokeDasharray="4 4"
                    fill="none"
                    name="Feels Like"
                  />
                </>
              )}
              {activeTab === "humidity" && (
                <Area
                  type="monotone"
                  dataKey="humidity"
                  stroke="#0284c7"
                  strokeWidth={2.5}
                  fillOpacity={1}
                  fill="url(#humidityGradient)"
                  name="Humidity"
                />
              )}
              {activeTab === "wind" && (
                <Area
                  type="monotone"
                  dataKey="wind"
                  stroke="#059669"
                  strokeWidth={2.5}
                  fillOpacity={1}
                  fill="url(#windGradient)"
                  name="Wind Speed"
                />
              )}
            </AreaChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default HourlyForecastPanel;
