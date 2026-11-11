import {
  Sprout,
  Layers,
  Thermometer,
  Activity,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

interface SoilMoistureDepth {
  depth_label: string;
  depth_code: string;
  moisture_m3m3: number;
  moisture_percentage: number;
  status: string;
}

interface SoilTemperatureDepth {
  depth_label: string;
  temperature_c: number;
}

interface AgriculturalWeatherProps {
  agricultural: {
    et0_today_mm: number;
    et0_weekly_total_mm: number;
    et0_interpretation: string;
    et0_trend: Array<{ date: string; day: string; et0: number; rain: number }>;
    soil_moisture_levels: SoilMoistureDepth[];
    soil_temperatures: SoilTemperatureDepth[];
    current_vpd_kpa: number;
    vpd_status: string;
    vpd_explanation: string;
    vpd_trend: Array<{ time: string; vpd: number; temp: number }>;
  };
}

export const AgriculturalWeatherPanel: React.FC<AgriculturalWeatherProps> = ({ agricultural }) => {
  const getSoilStatusColor = (status: string) => {
    if (status.includes("Dry")) return "#ef4444";
    if (status.includes("Moderate Deficit")) return "#f59e0b";
    if (status.includes("Adequate")) return "#10b981";
    return "#3b82f6";
  };

  const getVpdColor = (status: string) => {
    if (status.includes("Low")) return { bg: "#eff6ff", text: "#1d4ed8", border: "#bfdbfe" };
    if (status.includes("Optimal")) return { bg: "#f0fdf4", text: "#15803d", border: "#bbf7d0" };
    if (status.includes("Moderate")) return { bg: "#fefce8", text: "#a16207", border: "#fef08a" };
    if (status.includes("High")) return { bg: "#fff7ed", text: "#c2410c", border: "#fed7aa" };
    return { bg: "#fef2f2", text: "#b91c1c", border: "#fecaca" };
  };

  const vpdColors = getVpdColor(agricultural.vpd_status);

  return (
    <div className="weather-card">
      <div className="weather-card-header">
        <div className="weather-card-title-group">
          <div className="weather-card-title-icon">
            <Sprout size={18} />
          </div>
          <div>
            <h3 className="weather-card-title">Agricultural Weather Intelligence</h3>
            <span className="weather-card-subtitle">FAO-56 Evapotranspiration, Multi-depth Soil & Plant Transpiration Stress</span>
          </div>
        </div>
      </div>

      <div className="agri-intel-grid">
        {/* Card 1: Reference Evapotranspiration (ET0) */}
        <div style={{ background: "#ffffff", padding: "16px", borderRadius: "12px", border: "1px solid #e2e8f0" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "12px" }}>
            <div>
              <span style={{ fontSize: "0.78rem", textTransform: "uppercase", letterSpacing: "0.04em", color: "#64748b", fontWeight: 700 }}>
                Reference ET₀ (FAO-56)
              </span>
              <div style={{ fontSize: "2rem", fontWeight: 800, color: "#15803d", marginTop: "2px" }}>
                {agricultural.et0_today_mm} <small style={{ fontSize: "1rem", color: "#64748b", fontWeight: 500 }}>mm/day</small>
              </div>
            </div>
            <span className="location-chip" style={{ background: "rgba(22, 101, 52, 0.08)" }}>
              7-Day Sum: {agricultural.et0_weekly_total_mm} mm
            </span>
          </div>

          <p style={{ fontSize: "0.83rem", color: "#475569", lineHeight: 1.45, marginBottom: "14px" }}>
            {agricultural.et0_interpretation}
          </p>

          <span style={{ fontSize: "0.74rem", fontWeight: 700, color: "#64748b", textTransform: "uppercase" }}>
            7-Day ET₀ vs. Rainfall Forecast
          </span>

          <div style={{ height: 130, width: "100%", marginTop: "6px" }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={agricultural.et0_trend} margin={{ top: 5, right: 5, left: -25, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                <XAxis dataKey="day" tick={{ fontSize: 10, fill: "#64748b" }} />
                <YAxis tick={{ fontSize: 10, fill: "#64748b" }} unit="mm" />
                <Tooltip
                  formatter={(val: any, name: any) => [`${val} mm`, name === "et0" ? "ET₀ Demand" : "Rainfall"]}
                  labelFormatter={(lbl) => `Day: ${lbl}`}
                />
                <Bar dataKey="et0" fill="#22c55e" radius={[3, 3, 0, 0]} name="et0" />
                <Bar dataKey="rain" fill="#3b82f6" radius={[3, 3, 0, 0]} name="rain" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Card 2: Multi-Depth Soil Moisture Profile */}
        <div style={{ background: "#ffffff", padding: "16px", borderRadius: "12px", border: "1px solid #e2e8f0" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "14px" }}>
            <div>
              <span style={{ fontSize: "0.78rem", textTransform: "uppercase", letterSpacing: "0.04em", color: "#64748b", fontWeight: 700 }}>
                Soil Moisture Profile
              </span>
              <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "#0f172a" }}>
                Multi-Depth Volumetric Water
              </div>
            </div>
            <Layers size={18} color="#3b82f6" />
          </div>

          <div>
            {agricultural.soil_moisture_levels.map((lvl) => {
              const statusColor = getSoilStatusColor(lvl.status);
              return (
                <div key={lvl.depth_code} className="soil-depth-item">
                  <div className="soil-depth-header">
                    <span>{lvl.depth_label}</span>
                    <span>
                      <strong>{lvl.moisture_m3m3} m³/m³</strong> ({lvl.status})
                    </span>
                  </div>
                  <div className="soil-progress-track">
                    <div
                      className="soil-progress-fill"
                      style={{
                        width: `${lvl.moisture_percentage}%`,
                        backgroundColor: statusColor,
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>

          <div style={{ display: "flex", gap: "8px", marginTop: "10px", fontSize: "0.72rem", color: "#64748b", flexWrap: "wrap" }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: "3px" }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#10b981" }} /> Adequate
            </span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: "3px" }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#f59e0b" }} /> Moderate Deficit
            </span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: "3px" }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#ef4444" }} /> Below Refill
            </span>
          </div>
        </div>

        {/* Card 3: Soil Temperatures & Vapor Pressure Deficit (VPD) */}
        <div style={{ background: "#ffffff", padding: "16px", borderRadius: "12px", border: "1px solid #e2e8f0" }}>
          {/* VPD Section */}
          <div style={{ marginBottom: "16px", paddingBottom: "14px", borderBottom: "1px solid #f1f5f9" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
              <span style={{ fontSize: "0.78rem", textTransform: "uppercase", letterSpacing: "0.04em", color: "#64748b", fontWeight: 700 }}>
                Vapour Pressure Deficit (VPD)
              </span>
              <div
                className="vpd-badge-container"
                style={{
                  background: vpdColors.bg,
                  color: vpdColors.text,
                  border: `1px solid ${vpdColors.border}`,
                }}
              >
                <Activity size={13} />
                {agricultural.vpd_status}
              </div>
            </div>

            <div style={{ fontSize: "1.85rem", fontWeight: 800, color: "#1e293b" }}>
              {agricultural.current_vpd_kpa} <small style={{ fontSize: "0.9rem", color: "#64748b", fontWeight: 500 }}>kPa</small>
            </div>

            <p style={{ fontSize: "0.8rem", color: "#475569", marginTop: "4px", lineHeight: 1.4 }}>
              {agricultural.vpd_explanation}
            </p>
          </div>

          {/* Soil Temperatures */}
          <div>
            <span style={{ fontSize: "0.78rem", textTransform: "uppercase", letterSpacing: "0.04em", color: "#64748b", fontWeight: 700 }}>
              Soil Temperature Sensors
            </span>

            <div className="soil-temp-grid">
              {agricultural.soil_temperatures.map((st) => (
                <div key={st.depth_label} className="soil-temp-card">
                  <Thermometer size={16} color="#eab308" />
                  <div>
                    <div style={{ fontSize: "0.72rem", color: "#64748b" }}>{st.depth_label}</div>
                    <div className="soil-temp-val">{st.temperature_c}°C</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AgriculturalWeatherPanel;
