import React from "react";
import { AlertTriangle, AlertCircle, Info, ShieldCheck } from "lucide-react";

interface WeatherAlert {
  id: string;
  severity: string;
  category: string;
  title: string;
  message: string;
  recommendation: string;
  time_window: string;
}

interface WeatherAlertsPanelProps {
  alerts: WeatherAlert[];
}

export const WeatherAlertsPanel: React.FC<WeatherAlertsPanelProps> = ({ alerts }) => {
  if (alerts.length === 0) {
    return (
      <div className="weather-card">
        <div style={{ display: "flex", alignItems: "center", gap: "10px", padding: "10px 0", color: "#166534" }}>
          <ShieldCheck size={24} color="#16a34a" />
          <div>
            <h4 style={{ fontWeight: 700, fontSize: "0.95rem", margin: 0 }}>No Severe Weather Alerts Active</h4>
            <span style={{ fontSize: "0.8rem", color: "#64748b" }}>Current environmental parameters are within standard safe agricultural ranges.</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="weather-card">
      <div className="weather-card-header">
        <div className="weather-card-title-group">
          <div className="weather-card-title-icon" style={{ background: "#fee2e2", color: "#b91c1c" }}>
            <AlertTriangle size={18} />
          </div>
          <div>
            <h3 className="weather-card-title">Active Weather & Agronomic Alerts ({alerts.length})</h3>
            <span className="weather-card-subtitle">Real-time threshold triggers computed from ECMWF forecast</span>
          </div>
        </div>
      </div>

      <div>
        {alerts.map((alert) => {
          let sevClass = "alert-sev-advisory";
          let Icon = Info;
          if (alert.severity === "warning" || alert.severity === "critical") {
            sevClass = "alert-sev-warning";
            Icon = AlertTriangle;
          } else if (alert.severity === "caution") {
            sevClass = "alert-sev-caution";
            Icon = AlertCircle;
          }

          return (
            <div key={alert.id} className={`alert-card-item ${sevClass}`}>
              <Icon size={20} style={{ flexShrink: 0, marginTop: 2 }} />
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "6px" }}>
                  <span style={{ fontWeight: 700, fontSize: "0.92rem" }}>{alert.title}</span>
                  <span style={{ fontSize: "0.72rem", padding: "2px 8px", borderRadius: "10px", background: "rgba(0,0,0,0.06)", fontWeight: 600 }}>
                    {alert.time_window}
                  </span>
                </div>
                <p style={{ fontSize: "0.84rem", margin: "4px 0 6px", lineHeight: 1.45 }}>
                  {alert.message}
                </p>
                <div style={{ fontSize: "0.8rem", fontWeight: 600, display: "flex", alignItems: "center", gap: "6px" }}>
                  <span>Action:</span>
                  <span style={{ opacity: 0.95 }}>{alert.recommendation}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default WeatherAlertsPanel;
