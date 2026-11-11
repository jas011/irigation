import React, { useEffect, useState } from "react";
import { AlertTriangle, Loader2, MapPin } from "lucide-react";
import { useFieldContext } from "../layouts/DashboardLayout";
import ApiService from "../services/api";
import MoistureStress from "./DashboardSections/MoistureStress";
import { mapMoistureAnalysisToStressData } from "../utils/analysisMappers";
import {
  getCachedCropResult,
  getCachedMoistureResult,
  setCachedMoistureResult,
} from "../utils/analysisCache";
import StagePageWrapper from "../components/StageNavigation/StagePageWrapper";
import { AnalysisProgressCard } from "../components/Dashboard/AnalysisProgressCard";
import "./Dashboard.css";

const MoistureAnalysisPage: React.FC = () => {
  const { activeFieldId, selectedFieldData } = useFieldContext();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<any | null>(null);

  useEffect(() => {
    if (!activeFieldId || !selectedFieldData) {
      setError("A valid field and crop context are required before soil moisture analysis can begin.");
      setResult(null);
      return;
    }

    const cachedMoisture = getCachedMoistureResult(activeFieldId);
    if (cachedMoisture) {
      setResult(cachedMoisture);
      setError(null);
      return;
    }

    const run = async () => {
      const cropResult = getCachedCropResult(activeFieldId);
      if (!cropResult) {
        setError("Stage 2 crop results were not found. Please run crop analysis first.");
        setResult(null);
        return;
      }

      try {
        setLoading(true);
        setError(null);
        const response = await ApiService.analyzeMoistureStage(
          selectedFieldData.field_id,
          selectedFieldData.geometry,
          cropResult.cropPrediction?.label,
          cropResult.growthStage?.stage,
        );
        setResult(response);
        setCachedMoistureResult(activeFieldId, response);
      } catch (err: any) {
        setError(err?.message || "Moisture analysis failed.");
        setResult(null);
      } finally {
        setLoading(false);
      }
    };

    run();
  }, [activeFieldId, selectedFieldData]);

  if (loading) {
    return (
      <StagePageWrapper stageId="moisture">
        <AnalysisProgressCard
          type="moisture"
          fieldName={selectedFieldData?.field_name || activeFieldId}
        />
      </StagePageWrapper>
    );
  }

  if (!activeFieldId || !selectedFieldData) {
    return (
      <StagePageWrapper stageId="moisture">
        <div className="analysis-empty-card">
          <MapPin size={32} className="analysis-empty-icon" />
          <div>
            <h4>No field selected</h4>
            <p>
              Select a registered field from History or complete Area Selection to run moisture
              stress analysis.
            </p>
          </div>
        </div>
      </StagePageWrapper>
    );
  }

  if (error) {
    return (
      <StagePageWrapper stageId="moisture">
        <div className="analysis-error-card">
          <AlertTriangle size={24} className="analysis-error-icon" />
          <div className="analysis-error-content">
            <h4>Moisture analysis failed</h4>
            <p>{error}</p>
          </div>
        </div>
      </StagePageWrapper>
    );
  }

  if (!result) {
    return (
      <StagePageWrapper stageId="moisture">
        <div className="analysis-loading-card">
          <Loader2 size={28} className="analysis-loading-spinner" />
          <div>
            <h4>Preparing moisture analysis</h4>
            <p>Loading analysis data…</p>
          </div>
        </div>
      </StagePageWrapper>
    );
  }

  return (
    <StagePageWrapper stageId="moisture">
      <MoistureStress data={mapMoistureAnalysisToStressData(result, selectedFieldData.field_id)} />
    </StagePageWrapper>
  );
};

export default MoistureAnalysisPage;
