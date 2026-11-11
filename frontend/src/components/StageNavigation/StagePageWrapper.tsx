import React, { useEffect, useState } from "react";
import type { AnalysisStageId } from "../../constants/analysisStages";
import StageNavigation from "./StageNavigation";
import "./StageNavigation.css";

interface StagePageWrapperProps {
  stageId: AnalysisStageId;
  children: React.ReactNode;
}

const StagePageWrapper: React.FC<StagePageWrapperProps> = ({ stageId, children }) => {
  const [enterClass, setEnterClass] = useState("stage-page-enter");
  const [contentKey, setContentKey] = useState(stageId);

  useEffect(() => {
    const direction = sessionStorage.getItem("agrisense_stage_direction");
    setEnterClass(direction === "back" ? "stage-page-enter--back" : "stage-page-enter");
    sessionStorage.removeItem("agrisense_stage_direction");
    setContentKey(stageId);
  }, [stageId]);

  return (
    <div className={`dashboard-container stage-page-wrapper ${enterClass}`}>
      <div key={contentKey} className="stage-page-content">
        {children}
      </div>
      <StageNavigation currentStage={stageId} />
    </div>
  );
};

export default StagePageWrapper;
