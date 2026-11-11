import React from "react";
import { Clock, Droplets, Wind } from "lucide-react";
import WeatherIcon from "./WeatherIcon";

interface TimelinePeriod {
  period: string;
  time_range: string;
  temperature: number;
  condition: {
    label: string;
    description: string;
    icon_type: string;
    is_day: boolean;
  };
  precipitation_probability: number;
  rain_mm: number;
  relative_humidity: number;
  wind_speed: number;
}

interface WeatherTimelinePanelProps {
  timeline: TimelinePeriod[];
}

export const WeatherTimelinePanel: React.FC<WeatherTimelinePanelProps> = ({ timeline }) => {
  return (
    <div className="weather-card">
      <div className="weather-card-header">
        <div className="weather-card-title-group">
          <div className="weather-card-title-icon">
            <Clock size={18} />
          </div>
          <div>
            <h3 className="weather-card-title">Day Progression</h3>
            <span className="weather-card-subtitle">Diurnal cycle forecast overview</span>
          </div>
        </div>
      </div>

      <div className="timeline-card-grid">
        {timeline.map((item) => (
          <div key={item.period} className="timeline-period-item">
            <span className="timeline-period-name">{item.period}</span>
            <span className="timeline-period-range">{item.time_range}</span>

            <WeatherIcon
              iconType={item.condition.icon_type}
              isDay={item.condition.is_day}
              size={32}
            />

            <span className="timeline-period-temp">{item.temperature}°C</span>

            <span style={{ fontSize: "0.75rem", color: "#475569", fontWeight: 600 }}>
              {item.condition.label}
            </span>

            <div className="timeline-period-meta">
              <span style={{ display: "inline-flex", alignItems: "center", gap: "2px", color: item.precipitation_probability > 30 ? "#2563eb" : "#64748b" }}>
                <Droplets size={12} />
                {item.precipitation_probability}%
              </span>
              <span>•</span>
              <span style={{ display: "inline-flex", alignItems: "center", gap: "2px" }}>
                <Wind size={12} />
                {item.wind_speed} km/h
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default WeatherTimelinePanel;
