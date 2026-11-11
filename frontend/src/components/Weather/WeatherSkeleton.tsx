import React from "react";

export const WeatherSkeleton: React.FC = () => {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px", width: "100%" }}>
      {/* Top Header Skeleton */}
      <div className="weather-card" style={{ height: "90px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ width: "300px", height: "40px" }} className="weather-skeleton-box" />
        <div style={{ width: "200px", height: "40px" }} className="weather-skeleton-box" />
      </div>

      {/* Summary Skeleton */}
      <div className="weather-skeleton-box" style={{ height: "60px", borderRadius: "14px" }} />

      {/* Hero Grid Skeleton */}
      <div className="weather-hero-grid">
        <div className="weather-card" style={{ height: "260px" }}>
          <div className="weather-skeleton-box" style={{ height: "100%", width: "100%" }} />
        </div>
        <div className="weather-card" style={{ height: "260px" }}>
          <div className="weather-skeleton-box" style={{ height: "100%", width: "100%" }} />
        </div>
      </div>

      {/* Hourly Skeleton */}
      <div className="weather-card" style={{ height: "280px" }}>
        <div className="weather-skeleton-box" style={{ height: "100%", width: "100%" }} />
      </div>

      {/* Daily Skeleton */}
      <div className="weather-card" style={{ height: "350px" }}>
        <div className="weather-skeleton-box" style={{ height: "100%", width: "100%" }} />
      </div>
    </div>
  );
};

export default WeatherSkeleton;
