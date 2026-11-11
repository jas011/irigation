import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Trash2, Calendar, MapPin, CheckCircle, AlertCircle, ArrowUpRight, Layers, Lock } from "lucide-react";
import ApiService from "../services/api";
import { useFieldContext } from "../layouts/DashboardLayout";
import StageNavigation, { canAccessAnalysisStage } from "../components/StageNavigation/StageNavigation";
import { ANALYSIS_STAGES } from "../constants/analysisStages";
import type { AnalysisStageId } from "../constants/analysisStages";
import { hasCachedCropResult, hasCachedMoistureResult } from "../utils/analysisCache";

const History: React.FC = () => {
  const navigate = useNavigate();
  const { activeFieldId, setActiveFieldId, setSelectedFieldData, areaUnit } = useFieldContext();

  const [fields, setFields] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [previewStage, setPreviewStage] = useState<AnalysisStageId>("area");

  useEffect(() => {
    sessionStorage.removeItem("agrisense_from_history");
  }, []);

  const loadHistory = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await ApiService.listFields();
      setFields(data);
    } catch (err: any) {
      setError(err.message || "Failed to retrieve fields history.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadHistory();
  }, []);

  const handleSelectField = (field: any) => {
    setActiveFieldId(field.field_id);
    setSelectedFieldData(field);
  };

  const handleViewField = (field: any) => {
    handleSelectField(field);
    setPreviewStage("area");
    sessionStorage.setItem("agrisense_stage_direction", "forward");
    sessionStorage.setItem("agrisense_from_history", "true");
    navigate("/area-selection");
  };

  const handleBrowseAnalysis = (field: any) => {
    handleSelectField(field);
    setPreviewStage("area");
    sessionStorage.setItem("agrisense_stage_direction", "forward");
    sessionStorage.setItem("agrisense_from_history", "true");
    navigate("/area-selection");
  };

  const handleStageNavigate = (direction: "prev" | "next" | "jump", targetPath: string) => {
    const targetStage = ANALYSIS_STAGES.find((s) => s.path === targetPath);
    if (targetStage) {
      setPreviewStage(targetStage.id);
    }

    sessionStorage.setItem(
      "agrisense_stage_direction",
      direction === "prev" ? "back" : "forward",
    );
    sessionStorage.setItem("agrisense_from_history", "true");
    navigate(targetPath);
  };

  const handleQuickLink = (stageId: AnalysisStageId, path: string) => {
    if (!activeFieldId || !canAccessAnalysisStage(stageId, activeFieldId)) return;
    handleStageNavigate("jump", path);
  };

  const handleDeleteField = async (e: React.MouseEvent, fieldId: string) => {
    e.stopPropagation();
    if (!window.confirm(`Are you sure you want to delete Field ${fieldId}?`)) {
      return;
    }

    setActionLoading(fieldId);
    try {
      await ApiService.deleteField(fieldId);
      setFields((currentFields) => currentFields.filter((field) => field.field_id !== fieldId));
      setActiveFieldId((activeFieldId) => activeFieldId === fieldId ? null : activeFieldId);
      setSelectedFieldData((selectedField: any | null) => selectedField?.field_id === fieldId ? null : selectedField);
    } catch (err: any) {
      setError(err.message || "Could not delete field. Please try again.");
    } finally {
      setActionLoading(null);
    }
  };

  const formatArea = (hectares: number, acres: number) => {
    if (areaUnit === "acres") {
      return `${acres.toFixed(2)} ac`;
    }
    return `${hectares.toFixed(2)} ha`;
  };

  const formatDate = (dateStr: string) => {
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString("en-GB", {
        day: "2-digit",
        month: "short",
        year: "numeric"
      });
    } catch (e) {
      return dateStr;
    }
  };

  const getStageResultBadge = (stageId: AnalysisStageId): string | null => {
    if (!activeFieldId) return null;
    if (stageId === "crop" && hasCachedCropResult(activeFieldId)) return "Results ready";
    if (stageId === "moisture" && hasCachedMoistureResult(activeFieldId)) return "Results ready";
    return null;
  };

  return (
    <div className="history-page">
      <div className="history-card">
        <span className="history-kicker"><Layers size={14} /> FIELD OPERATIONS</span>
        <h3 className="history-header">Registered Fields Library</h3>
        <p className="history-subtitle">
          Manage your registered fields. Select a field, then use the analysis navigator below to browse area selection, crop classification, and moisture results at any time.
        </p>
        <div className="history-overview">
          <div className="history-overview-item">
            <span className="history-overview-label">Registered fields</span>
            <strong>{fields.length}</strong>
          </div>
          <div className="history-overview-item">
            <span className="history-overview-label">Active workspace</span>
            <strong>{activeFieldId || "None selected"}</strong>
          </div>
          <div className="history-overview-item">
            <span className="history-overview-label">Analysis access</span>
            <strong>{activeFieldId ? "Ready" : "Select a field"}</strong>
          </div>
        </div>
      </div>

      {error && (
        <div className="alert-container alert-danger">
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}

      {isLoading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          {[1, 2, 3].map((n) => (
            <div key={n} className="loading-skeleton" />
          ))}
        </div>
      ) : fields.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">
            <MapPin size={28} />
          </div>
          <div>
            <h4 className="empty-state-title">No Fields Registered Yet</h4>
            <p className="empty-state-text">
              Draw your agricultural field boundaries on the dashboard and confirm them to register.
            </p>
          </div>
          <button onClick={() => navigate("/")} className="confirm-btn" style={{ width: "auto", padding: "10px 20px" }}>
            Go to Dashboard
          </button>
        </div>
      ) : (
        <div className="history-card" style={{ overflow: "hidden" }}>
          <div style={{ overflowX: "auto" }}>
            <table className="history-table" style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "14px" }}>
              <thead>
                <tr style={{ backgroundColor: "#f8fafc", borderBottom: "1px solid var(--border-color)", color: "var(--text-muted)", fontWeight: 600 }}>
                  <th style={{ padding: "16px 20px" }}>Field ID</th>
                  <th style={{ padding: "16px 20px" }}>Location</th>
                  <th style={{ padding: "16px 20px" }}>Area</th>
                  <th style={{ padding: "16px 20px" }}>Perimeter</th>
                  <th style={{ padding: "16px 20px" }}>Date Registered</th>
                  <th style={{ padding: "16px 20px" }}>Status</th>
                  <th style={{ padding: "16px 20px", textAlign: "right" }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {fields.map((field) => (
                  <tr
                    key={field.id}
                    onClick={() => handleSelectField(field)}
                    className={`history-row ${activeFieldId === field.field_id ? "history-row--selected" : ""}`}
                  >
                    <td style={{ padding: "16px 20px", fontWeight: 700, color: "var(--primary-green)", fontFamily: "monospace" }}>
                      {field.field_id}
                    </td>

                    <td style={{ padding: "16px 20px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                        <MapPin size={16} color="var(--text-muted)" />
                        <span>
                          {field.village ? `${field.village}, ` : ""}
                          {field.district ? `${field.district}, ` : ""}
                          {field.state || field.country || "Unknown Location"}
                        </span>
                      </div>
                    </td>

                    <td style={{ padding: "16px 20px", fontWeight: 600 }}>
                      {formatArea(field.area_hectares, field.area_acres)}
                    </td>

                    <td style={{ padding: "16px 20px", color: "var(--text-muted)" }}>
                      {(field.perimeter_m / 1000).toFixed(2)} km
                    </td>

                    <td style={{ padding: "16px 20px", color: "var(--text-muted)" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                        <Calendar size={14} />
                        <span>{formatDate(field.created_at)}</span>
                      </div>
                    </td>

                    <td style={{ padding: "16px 20px" }}>
                      <span style={{ display: "inline-flex", alignItems: "center", gap: "4px", padding: "4px 10px", borderRadius: "20px", backgroundColor: "#ecfdf5", color: "#047857", fontSize: "12px", fontWeight: 600 }}>
                        <CheckCircle size={12} />
                        <span>Ready for Analysis</span>
                      </span>
                    </td>

                    <td style={{ padding: "16px 20px", textAlign: "right" }} onClick={(e) => e.stopPropagation()}>
                      <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end" }}>
                        <button
                          onClick={() => handleViewField(field)}
                          style={{
                            padding: "6px",
                            borderRadius: "6px",
                            border: "1px solid var(--border-color)",
                            backgroundColor: "var(--bg-primary)",
                            color: "var(--text-main)"
                          }}
                          title="View on Dashboard Map"
                          className="action-icon-btn"
                        >
                          <ArrowUpRight size={16} />
                        </button>
                        <button
                          onClick={() => handleBrowseAnalysis(field)}
                          style={{
                            padding: "6px 10px",
                            borderRadius: "6px",
                            border: "1px solid #bbf7d0",
                            backgroundColor: "#ecfdf5",
                            color: "#166534",
                            fontSize: "12px",
                            fontWeight: 600,
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "4px",
                          }}
                          title="Browse full analysis stages"
                          className="action-icon-btn"
                        >
                          <Layers size={14} />
                          Browse
                        </button>
                        <button
                          onClick={(e) => handleDeleteField(e, field.field_id)}
                          style={{
                            padding: "6px",
                            borderRadius: "6px",
                            border: "1px solid #fecaca",
                            backgroundColor: "#fff5f5",
                            color: "#dc2626"
                          }}
                          disabled={actionLoading === field.field_id}
                          title="Delete Field"
                          className="action-icon-btn delete-icon-btn"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {fields.length > 0 && (
        <div className="history-analysis-nav">
          <div className="history-analysis-nav-header">
            <Layers size={18} color="#166534" />
            <div>
              <h4>Analysis Stage Navigator</h4>
              <p>
                {activeFieldId
                  ? `Browsing stages for ${activeFieldId}. Use Previous / Next or tap a stage to jump.`
                  : "Select a field above to unlock stage navigation."}
              </p>
            </div>
          </div>
          <StageNavigation
            variant="history"
            currentStage={previewStage}
            onNavigate={handleStageNavigate}
          />
          {activeFieldId && (
            <div className="history-stage-quick-links">
              {ANALYSIS_STAGES.map((stage) => {
                const accessible = canAccessAnalysisStage(stage.id, activeFieldId);
                const resultBadge = getStageResultBadge(stage.id);
                const isActive = previewStage === stage.id;

                return (
                  <button
                    key={stage.id}
                    type="button"
                    className={`history-stage-quick-link ${isActive ? "history-stage-quick-link--active" : ""} ${!accessible ? "history-stage-quick-link--locked" : ""}`}
                    disabled={!accessible}
                    onClick={() => handleQuickLink(stage.id, stage.path)}
                    title={
                      accessible
                        ? stage.description
                        : "Complete crop analysis first to unlock moisture stage"
                    }
                  >
                    {!accessible && <Lock size={12} />}
                    {stage.label}
                    {resultBadge && (
                      <span className="history-stage-quick-link-badge">{resultBadge}</span>
                    )}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default History;
