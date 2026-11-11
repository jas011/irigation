import React from "react";
import {
  Droplets,
  AlertCircle,
  CheckCircle2,
  HelpCircle,
} from "lucide-react";

interface IrrigationOutlookProps {
  outlook: {
    forecast_rainfall_48h_mm: number;
    forecast_rainfall_72h_mm: number;
    forecast_et0_48h_mm: number;
    forecast_et0_72h_mm: number;
    net_atmospheric_deficit_48h_mm: number;
    net_atmospheric_deficit_72h_mm: number;
    rain_probability_max_48h: number;
    upcoming_dry_days_count: number;
    risk_level: string;
    advisory_headline: string;
    advisory_body: string;
    field_actions: string[];
    scientific_disclaimer: string;
  };
}

export const IrrigationOutlookPanel: React.FC<IrrigationOutlookProps> = ({ outlook }) => {
  return (
    <div className="weather-card">
      <div className="weather-card-header">
        <div className="weather-card-title-group">
          <div className="weather-card-title-icon">
            <Droplets size={18} />
          </div>
          <div>
            <h3 className="weather-card-title">Irrigation Weather Outlook</h3>
            <span className="weather-card-subtitle">Atmospheric Water Balance & Field Scheduling Guidance</span>
          </div>
        </div>

        <div className={`irrigation-risk-badge irrigation-risk-${outlook.risk_level}`}>
          <AlertCircle size={14} />
          <span>Irrigation Demand Risk: {outlook.risk_level}</span>
        </div>
      </div>

      <div className="irrigation-outlook-box">
        <h4 style={{ fontSize: "1.05rem", fontWeight: 700, color: "#14532d", marginBottom: "6px" }}>
          {outlook.advisory_headline}
        </h4>

        <p style={{ fontSize: "0.88rem", color: "#334155", lineHeight: 1.5 }}>
          {outlook.advisory_body}
        </p>

        {/* Atmospheric Water Balance Metrics */}
        <div className="water-balance-strip">
          <div className="balance-item">
            <span className="balance-label">48h Rain Forecast</span>
            <span className="balance-val" style={{ color: "#2563eb" }}>
              {outlook.forecast_rainfall_48h_mm} mm
            </span>
          </div>

          <div className="balance-item">
            <span className="balance-label">48h ET₀ Demand</span>
            <span className="balance-val" style={{ color: "#15803d" }}>
              {outlook.forecast_et0_48h_mm} mm
            </span>
          </div>

          <div className="balance-item">
            <span className="balance-label">48h Net Deficit</span>
            <span className="balance-val" style={{ color: outlook.net_atmospheric_deficit_48h_mm > 6 ? "#ea580c" : "#1e293b" }}>
              {outlook.net_atmospheric_deficit_48h_mm > 0 ? `-${outlook.net_atmospheric_deficit_48h_mm}` : `+${Math.abs(outlook.net_atmospheric_deficit_48h_mm)}`} mm
            </span>
          </div>

          <div className="balance-item">
            <span className="balance-label">48h Rain Probability</span>
            <span className="balance-val" style={{ color: "#4f46e5" }}>
              {outlook.rain_probability_max_48h}%
            </span>
          </div>

          <div className="balance-item">
            <span className="balance-label">7-Day Dry Window</span>
            <span className="balance-val" style={{ color: "#64748b" }}>
              {outlook.upcoming_dry_days_count} Days
            </span>
          </div>
        </div>

        {/* Recommended Field Actions */}
        {outlook.field_actions.length > 0 && (
          <div style={{ marginTop: "14px" }}>
            <span style={{ fontSize: "0.8rem", fontWeight: 700, color: "#166534", textTransform: "uppercase", letterSpacing: "0.03em" }}>
              Recommended Agronomic Actions
            </span>

            <div className="irrigation-action-list">
              {outlook.field_actions.map((act, i) => (
                <div key={i} className="irrigation-action-item">
                  <CheckCircle2 size={16} color="#16a34a" style={{ flexShrink: 0, marginTop: 2 }} />
                  <span>{act}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Transparent Disclaimer */}
        <div style={{ display: "flex", alignItems: "flex-start", gap: "8px", marginTop: "16px", padding: "10px 12px", background: "rgba(255,255,255,0.6)", borderRadius: "8px", border: "1px solid #e2e8f0", fontSize: "0.76rem", color: "#64748b" }}>
          <HelpCircle size={15} style={{ flexShrink: 0, marginTop: 1, color: "#94a3b8" }} />
          <span>{outlook.scientific_disclaimer}</span>
        </div>
      </div>
    </div>
  );
};

export default IrrigationOutlookPanel;
