import React, { useEffect, useMemo } from "react";
import L from "leaflet";
import { MapContainer, Polygon, TileLayer, GeoJSON, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";

interface ResultMapProps {
  geometry: any;
  overlay: any;
  mode: "crop" | "moisture";
  stressLevel?: string;
  stressScore?: number;
  crop?: string | null;
}

const fixedCropColors: Record<string, string> = {
  Paddy: "#10b981",
  "Paddy/Rice": "#10b981",
  Wheat: "#eab308",
  Cotton: "#06b6d4",
  Maize: "#f97316",
  "Bare Soil": "#78350f",
  Water: "#3b82f6",
  "Non-Crop": "#6b7280",
  "Other Crop": "#a855f7",
};
const cropPalette = ["#a855f7", "#ec4899", "#f97316", "#14b8a6", "#6366f1", "#84cc16", "#0ea5e9", "#e11d48"];
const cropColor = (crop?: string | null) => {
  if (!crop) return "#10b981";
  if (fixedCropColors[crop]) return fixedCropColors[crop];
  const hash = [...crop].reduce((value, character) => ((value * 31) + character.charCodeAt(0)) >>> 0, 0);
  return cropPalette[hash % cropPalette.length];
};

const stressColor = (stress?: string, score?: number) => {
  if (score !== undefined && score !== null && !isNaN(score)) {
    if (score < 20) return "#3b82f6"; // No Stress (Blue)
    if (score < 40) return "#22c55e"; // Low Stress (Green)
    if (score < 60) return "#eab308"; // Moderate Stress (Yellow)
    if (score < 80) return "#f97316"; // High Stress (Orange)
    return "#ef4444"; // Severe Stress (Red)
  }
  const colorMap: Record<string, string> = {
    "No Stress": "#3b82f6",
    "Low Stress": "#22c55e",
    "Moderate Stress": "#eab308",
    "High Stress": "#f97316",
    "Severe Stress": "#ef4444",
  };
  return colorMap[stress || ""] || "#22c55e";
};

const FitFieldBounds: React.FC<{ positions: [number, number][] }> = ({ positions }) => {
  const map = useMap();
  useEffect(() => {
    if (positions.length > 2) {
      map.fitBounds(positions, { padding: [18, 18], maxZoom: 17 });
    }
  }, [map, positions]);
  return null;
};

const ResultMap: React.FC<ResultMapProps> = ({ geometry, overlay, mode, stressLevel, stressScore, crop }) => {
  const coordinates = geometry?.coordinates?.[0] || [];
  const positions = coordinates.map((point: number[]) => [point[1], point[0]] as [number, number]);
  const center = useMemo<[number, number]>(() => {
    if (positions.length) {
      const lat = positions.reduce((sum: number, point: [number, number]) => sum + point[0], 0) / positions.length;
      const lng = positions.reduce((sum: number, point: [number, number]) => sum + point[1], 0) / positions.length;
      return [lat, lng];
    }
    return [30.901, 75.8573];
  }, [geometry]);

  const fieldColor = mode === "crop"
    ? cropColor(crop)
    : stressColor(stressLevel, stressScore);

  return (
    <div className="result-map-card">
      <div className="result-map-heading">
        <div>
          <span className="result-map-kicker">{mode === "crop" ? "Spatial output" : "Spatial stress output"}</span>
          <h3>{mode === "crop" ? "Crop Classification Map" : "Moisture Stress Map"}</h3>
        </div>
        <span className={`result-map-badge ${overlay?.features?.length ? "is-ready" : "is-ready"}`}>
          {overlay?.features?.length ? `${overlay.features.length} pixels` : (stressLevel || crop || "Field region")}
        </span>
      </div>
      <div className="result-map-viewport">
        <MapContainer center={center} zoom={15} scrollWheelZoom={false} zoomControl={false}>
          <FitFieldBounds positions={positions} />
          <TileLayer
            attribution="&copy; Esri"
            url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
          />
          {positions.length > 2 && (
            <Polygon
              positions={positions}
              pathOptions={{
                color: fieldColor,
                weight: 2.5,
                fillColor: fieldColor,
                fillOpacity: overlay?.features?.length > 0 ? 0.3 : 0.65
              }}
            />
          )}
          {overlay?.features?.length > 0 && (
            <GeoJSON
              key={`${mode}-${overlay.features.length}`}
              data={overlay}
              style={(feature: any) => {
                const color = mode === "crop"
                  ? cropColor(feature?.properties?.crop)
                  : stressColor(feature?.properties?.stress_class, feature?.properties?.stress_score);
                return {
                  color,
                  fillColor: color,
                  fillOpacity: 0.86,
                  weight: 0.7,
                };
              }}
              pointToLayer={(feature: any, latlng: L.LatLng) => {
                const color = mode === "crop"
                  ? cropColor(feature?.properties?.crop)
                  : stressColor(feature?.properties?.stress_class, feature?.properties?.stress_score);
                return L.circle(latlng, {
                  radius: 7,
                  color,
                  fillColor: color,
                  fillOpacity: 0.88,
                  weight: 1,
                });
              }}
            />
          )}
        </MapContainer>
      </div>
    </div>
  );
};

export default ResultMap;
