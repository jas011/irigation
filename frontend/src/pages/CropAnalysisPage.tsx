import React, { useEffect, useState } from "react";
import { AlertTriangle, Loader2, MapPin } from "lucide-react";
import { useFieldContext } from "../layouts/DashboardLayout";
import ApiService from "../services/api";
import CropClassification from "./DashboardSections/CropClassification";
import { mapCropAnalysisToClassificationData } from "../utils/analysisMappers";
import { getCachedCropResult, setCachedCropResult } from "../utils/analysisCache";
import StagePageWrapper from "../components/StageNavigation/StagePageWrapper";
import { AnalysisProgressCard } from "../components/Dashboard/AnalysisProgressCard";
import "./Dashboard.css";

const CropAnalysisPage: React.FC = () => {
  const { activeFieldId, selectedFieldData } = useFieldContext();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<any | null>(null);

  useEffect(() => {
    if (!activeFieldId || !selectedFieldData) {
      setError("A valid field selection is required before crop analysis can begin.");
      setResult(null);
      return;
    }

    const cached = getCachedCropResult(activeFieldId);
    if (cached) {
      setResult(cached);
      setError(null);
      return;
    }

    const run = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await ApiService.analyzeCropStage(
          selectedFieldData.field_id,
          selectedFieldData.geometry,
        );
        setResult(response);
        setCachedCropResult(activeFieldId, response);
      } catch (err: any) {
        setError(err?.message || "Crop analysis failed.");
        setResult(null);
      } finally {
        setLoading(false);
      }
    };

    run();
  }, [activeFieldId, selectedFieldData]);

  if (loading) {
    return (
      <StagePageWrapper stageId="crop">
        <AnalysisProgressCard
          type="crop"
          fieldName={selectedFieldData?.field_name || activeFieldId}
        />
      </StagePageWrapper>
    );
  }

  if (!activeFieldId || !selectedFieldData) {
    return (
      <StagePageWrapper stageId="crop">
        <div className="analysis-empty-card">
          <MapPin size={32} className="analysis-empty-icon" />
          <div>
            <h4>No field selected</h4>
            <p>
              Select a registered field from History or draw a boundary on the Area Selection
              page to run crop classification.
            </p>
          </div>
        </div>
      </StagePageWrapper>
    );
  }

  if (error) {
    return (
      <StagePageWrapper stageId="crop">
        <div className="analysis-error-card">
          <AlertTriangle size={24} className="analysis-error-icon" />
          <div className="analysis-error-content">
            <h4>Crop analysis failed</h4>
            <p>{error}</p>
          </div>
        </div>
      </StagePageWrapper>
    );
  }

  if (!result) {
    return (
      <StagePageWrapper stageId="crop">
        <div className="analysis-loading-card">
          <Loader2 size={28} className="analysis-loading-spinner" />
          <div>
            <h4>Preparing crop analysis</h4>
            <p>Loading analysis data…</p>
          </div>
        </div>
      </StagePageWrapper>
    );
  }

  return (
    <StagePageWrapper stageId="crop">
      <CropClassification data={mapCropAnalysisToClassificationData(result)} />
    </StagePageWrapper>
  );
};

export default CropAnalysisPage;
