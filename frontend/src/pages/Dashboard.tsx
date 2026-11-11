import React from "react";
import AreaSelection from "./DashboardSections/AreaSelection";
import StagePageWrapper from "../components/StageNavigation/StagePageWrapper";
import "./Dashboard.css";

const Dashboard: React.FC = () => {
  return (
    <StagePageWrapper stageId="area">
      <AreaSelection />
    </StagePageWrapper>
  );
};

export default Dashboard;
