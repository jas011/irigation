import React, { useState } from "react";
import {
  Calendar,
  ChevronDown,
  ChevronUp,
  CloudRain,
  Wind,
  Sunrise,
  Sunset,
} from "lucide-react";
import WeatherIcon from "./WeatherIcon";

interface DailyItem {
  date: string;
  day_name: string;
  formatted_date: string;
  weather_code: number;
  condition: {
    label: string;
    description: string;
    icon_type: string;
    is_day: boolean;
  };
  temp_max: number;
  temp_min: number;
  apparent_temp_max: number;
  apparent_temp_min: number;
  sunrise: string;
  sunset: string;
  daylight_duration_hours: number;
  sunshine_duration_hours: number;
  uv_index_max: number;
  precipitation_sum: number;
  precipitation_probability_max: number;
  wind_speed_max: number;
  wind_gusts_max: number;
  wind_direction_cardinal: string;
  et0_fao_sum?: number | null;
}

interface DailyForecastPanelProps {
  daily: DailyItem[];
}

export const DailyForecastPanel: React.FC<DailyForecastPanelProps> = ({ daily }) => {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  const toggleExpand = (idx: number) => {
    setExpandedIndex(expandedIndex === idx ? null : idx);
  };

  // Find min and max across all days for normalized temp bar
  const globalMin = Math.min(...daily.map((d) => d.temp_min), 15);
  const globalMax = Math.max(...daily.map((d) => d.temp_max), 38);
  const tempRange = globalMax - globalMin || 1;

  return (
    <div className="weather-card">
      <div className="weather-card-header">
        <div className="weather-card-title-group">
          <div className="weather-card-title-icon">
            <Calendar size={18} />
          </div>
          <div>
            <h3 className="weather-card-title">10-Day Medium-Range Outlook</h3>
            <span className="weather-card-subtitle">ECMWF IFS synchronized agricultural projection</span>
          </div>
        </div>
      </div>

      <div className="daily-forecast-list">
        {daily.map((day, idx) => {
          const isExpanded = expandedIndex === idx;
          const barLeftPct = Math.max(0, ((day.temp_min - globalMin) / tempRange) * 100);
          const barWidthPct = Math.max(10, ((day.temp_max - day.temp_min) / tempRange) * 100);

          return (
            <div
              key={day.date}
              className="daily-forecast-item"
              onClick={() => toggleExpand(idx)}
            >
              <div className="daily-row-main">
                {/* Day / Date */}
                <div>
                  <div className="daily-day-label">
                    {idx === 0 ? "Today" : idx === 1 ? "Tomorrow" : day.day_name}
                  </div>
                  <div className="daily-date-sub">{day.formatted_date}</div>
                </div>

                {/* Condition Icon & Label */}
                <div className="daily-condition-col">
                  <WeatherIcon
                    iconType={day.condition.icon_type}
                    size={24}
                  />
                  <span>{day.condition.label}</span>
                </div>

                {/* Min / Max Temp Bar */}
                <div className="daily-temp-bar-col">
                  <span className="daily-temp-min">{day.temp_min}°</span>
                  <div className="daily-temp-visual-bar">
                    <div
                      className="daily-temp-bar-fill"
                      style={{
                        marginLeft: `${barLeftPct}%`,
                        width: `${barWidthPct}%`,
                      }}
                    />
                  </div>
                  <span className="daily-temp-max">{day.temp_max}°</span>
                </div>

                {/* Precipitation */}
                <div className="daily-extra-col" style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.82rem", color: day.precipitation_probability_max > 25 ? "#2563eb" : "#64748b" }}>
                  <CloudRain size={14} />
                  <span>{day.precipitation_probability_max}% ({day.precipitation_sum} mm)</span>
                </div>

                {/* Wind */}
                <div className="daily-extra-col" style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: "0.82rem", color: "#475569" }}>
                  <Wind size={14} />
                  <span>{day.wind_speed_max} km/h</span>
                </div>

                {/* Expand Toggle */}
                <div style={{ textAlign: "right", color: "#94a3b8" }}>
                  {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                </div>
              </div>

              {/* Expandable Details Drawer */}
              {isExpanded && (
                <div className="daily-expanded-drawer">
                  <div>
                    <span style={{ fontSize: "0.74rem", color: "#64748b" }}>Feels Like Range:</span>
                    <div style={{ fontWeight: 600, fontSize: "0.85rem", color: "#1e293b" }}>
                      {day.apparent_temp_min}°C – {day.apparent_temp_max}°C
                    </div>
                  </div>

                  <div>
                    <span style={{ fontSize: "0.74rem", color: "#64748b" }}>Sun Times (IST):</span>
                    <div style={{ fontWeight: 600, fontSize: "0.85rem", color: "#1e293b", display: "flex", alignItems: "center", gap: "6px" }}>
                      <Sunrise size={13} color="#f59e0b" /> {day.sunrise.split("T")[1]?.slice(0, 5) || day.sunrise}
                      <Sunset size={13} color="#ea580c" /> {day.sunset.split("T")[1]?.slice(0, 5) || day.sunset}
                    </div>
                  </div>

                  <div>
                    <span style={{ fontSize: "0.74rem", color: "#64748b" }}>Daylight / Sunshine:</span>
                    <div style={{ fontWeight: 600, fontSize: "0.85rem", color: "#1e293b" }}>
                      {day.daylight_duration_hours}h / {day.sunshine_duration_hours}h
                    </div>
                  </div>

                  <div>
                    <span style={{ fontSize: "0.74rem", color: "#64748b" }}>Max Wind Gusts:</span>
                    <div style={{ fontWeight: 600, fontSize: "0.85rem", color: "#1e293b" }}>
                      {day.wind_gusts_max} km/h ({day.wind_direction_cardinal})
                    </div>
                  </div>

                  {day.et0_fao_sum !== null && day.et0_fao_sum !== undefined && (
                    <div>
                      <span style={{ fontSize: "0.74rem", color: "#64748b" }}>Atmospheric ET₀:</span>
                      <div style={{ fontWeight: 700, fontSize: "0.85rem", color: "#15803d" }}>
                        {day.et0_fao_sum} mm/day
                      </div>
                    </div>
                  )}

                  <div>
                    <span style={{ fontSize: "0.74rem", color: "#64748b" }}>Max UV Index:</span>
                    <div style={{ fontWeight: 600, fontSize: "0.85rem", color: day.uv_index_max >= 8 ? "#ef4444" : "#f59e0b" }}>
                      {day.uv_index_max} ({day.uv_index_max >= 8 ? "Very High" : day.uv_index_max >= 6 ? "High" : "Moderate"})
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default DailyForecastPanel;
