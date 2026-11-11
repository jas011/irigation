import React from "react";
import {
  Sun,
  Moon,
  CloudSun,
  CloudMoon,
  Cloud,
  CloudRain,
  CloudLightning,
  CloudFog,
  CloudDrizzle,
  Snowflake,
} from "lucide-react";

interface WeatherIconProps {
  iconType: string;
  isDay?: boolean;
  size?: number;
  className?: string;
}

export const WeatherIcon: React.FC<WeatherIconProps> = ({
  iconType,
  isDay = true,
  size = 28,
  className = "",
}) => {
  switch (iconType) {
    case "sunny":
    case "mostly_sunny":
      return isDay ? (
        <Sun size={size} color="#f59e0b" className={`weather-icon-sun ${className}`} />
      ) : (
        <Moon size={size} color="#93c5fd" className={`weather-icon-moon ${className}`} />
      );

    case "clear_night":
      return <Moon size={size} color="#93c5fd" className={`weather-icon-moon ${className}`} />;

    case "partly_cloudy":
      return isDay ? (
        <CloudSun size={size} color="#15803d" className={`weather-icon-cloudsun ${className}`} />
      ) : (
        <CloudMoon size={size} color="#60a5fa" className={`weather-icon-cloudmoon ${className}`} />
      );

    case "partly_cloudy_night":
      return <CloudMoon size={size} color="#60a5fa" className={`weather-icon-cloudmoon ${className}`} />;

    case "cloudy":
      return <Cloud size={size} color="#64748b" className={`weather-icon-cloud ${className}`} />;

    case "drizzle":
      return <CloudDrizzle size={size} color="#0284c7" className={`weather-icon-drizzle ${className}`} />;

    case "rain":
      return <CloudRain size={size} color="#2563eb" className={`weather-icon-rain ${className}`} />;

    case "heavy_rain":
      return <CloudRain size={size} color="#1d4ed8" strokeWidth={2.5} className={`weather-icon-heavyrain ${className}`} />;

    case "thunderstorm":
      return <CloudLightning size={size} color="#7c3aed" className={`weather-icon-thunder ${className}`} />;

    case "fog":
      return <CloudFog size={size} color="#94a3b8" className={`weather-icon-fog ${className}`} />;

    case "snow":
      return <Snowflake size={size} color="#38bdf8" className={`weather-icon-snow ${className}`} />;

    default:
      return isDay ? <Sun size={size} color="#f59e0b" /> : <Moon size={size} color="#93c5fd" />;
  }
};

export default WeatherIcon;
