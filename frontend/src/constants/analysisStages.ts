export type AnalysisStageId = "area" | "crop" | "moisture";

export interface AnalysisStage {
  id: AnalysisStageId;
  path: string;
  label: string;
  shortLabel: string;
  description: string;
}

export const ANALYSIS_STAGES: AnalysisStage[] = [
  {
    id: "area",
    path: "/area-selection",
    label: "Area Selection",
    shortLabel: "Area",
    description: "Define your field boundary",
  },
  {
    id: "crop",
    path: "/crop-analysis",
    label: "Crop Classification",
    shortLabel: "Crop",
    description: "Satellite crop & growth stage",
  },
  {
    id: "moisture",
    path: "/moisture-analysis",
    label: "Moisture Stress",
    shortLabel: "Moisture",
    description: "Soil moisture stress analysis",
  },
];

export const getStageByPath = (pathname: string): AnalysisStage | undefined =>
  ANALYSIS_STAGES.find((stage) => stage.path === pathname);

export const getStageIndex = (stageId: AnalysisStageId): number =>
  ANALYSIS_STAGES.findIndex((stage) => stage.id === stageId);
