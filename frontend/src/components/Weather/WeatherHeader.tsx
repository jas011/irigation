import React from "react";
import {
  CloudSun,
  MapPin,
  RefreshCw,
  Cpu,
  Layers,
} from "lucide-react";

interface WeatherHeaderProps {
  location: {
    field_id?: string | null;
    field_name?: string | null;
    village?: string | null;
    tehsil?: string | null;
    district?: string | null;
    state?: string | null;
    country?: string | null;
    area_hectares?: number | null;
    area_acres?: number | null;
    latitude: number;
    longitude: number;
  };
  metadata: {
    primary_model: string;
    grid_resolution: string;
    fetched_at_ist: string;
  };
  availableFields: any[];
  onSelectField: (fieldId: string) => void;
  onRefresh: () => void;
  isRefreshing: boolean;
}

export const WeatherHeader: React.FC<WeatherHeaderProps> = ({
  location,
  metadata,
  availableFields,
  onSelectField,
  onRefresh,
  isRefreshing,
}) => {
  const locationParts = [
    location.village,
    location.tehsil,
    location.district,
    location.state,
  ].filter(Boolean);

  const locationTitle = locationParts.length > 0 ? locationParts.join(" • ") : "Field Coordinates";

  return (
    <header className="weather-top-bar">
      {/* Title & Location chips */}
      <div className="weather-title-area">
        <h1 className="weather-main-heading">
          <CloudSun size={28} color="#15803d" />
          Weather Intelligence
        </h1>

        <div className="weather-location-chips">
          <span className="location-chip">
            <MapPin size={14} />
            {location.field_name ? `${location.field_name} — ` : ""}
            {locationTitle}
          </span>

          <span className="coord-chip">
            {location.latitude.toFixed(5)}° N, {location.longitude.toFixed(5)}° E
          </span>

          {location.area_hectares && (
            <span className="location-chip" style={{ background: "rgba(34, 197, 94, 0.12)" }}>
              <Layers size={13} />
              {location.area_hectares} ha ({location.area_acres || (location.area_hectares * 2.471).toFixed(1)} ac)
            </span>
          )}
        </div>
      </div>

      {/* Right Controls: Field Dropdown, Model Info, Refresh */}
      <div className="weather-actions-group">
        {/* Saved Field Switcher */}
        {availableFields.length > 0 && (
          <select
            className="field-select-dropdown"
            value={location.field_id || ""}
            onChange={(e) => onSelectField(e.target.value)}
            aria-label="Switch active field"
          >
            <option value="" disabled>Switch Field...</option>
            {availableFields.map((f) => (
              <option key={f.field_id} value={f.field_id}>
                {f.field_name || `Field ${f.field_id}`} ({f.village || f.district || "Custom"})
              </option>
            ))}
          </select>
        )}

        {/* Model Transparency Badge */}
        <div className="weather-model-badge">
          <div className="model-badge-name">
            <span className="model-dot" />
            <Cpu size={13} color="#15803d" />
            {metadata.primary_model}
          </div>
          <span>Updated {metadata.fetched_at_ist.split(" ")[1]} IST ({metadata.grid_resolution})</span>
        </div>

        {/* Refresh Button */}
        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          className={`weather-refresh-btn ${isRefreshing ? "spinning" : ""}`}
          title="Fetch latest forecast from ECMWF model"
        >
          <RefreshCw size={15} />
          <span>{isRefreshing ? "Refreshing..." : "Refresh"}</span>
        </button>
      </div>
    </header>
  );
};

export default WeatherHeader;
