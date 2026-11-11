import React, { useState, useEffect } from "react";
import {
  Loader2,
  CheckCircle2,
  Satellite,
  Radio,
  Sparkles,
  Layers,
  Thermometer,
  Droplets,
  Wheat,
  Activity,
  Terminal,
  Compass,
} from "lucide-react";
import "./AnalysisProgressCard.css";

interface AnalysisProgressCardProps {
  type: "crop" | "moisture";
  fieldName?: string;
}

interface StepItem {
  id: string;
  label: string;
  detail: string;
  sensor: string;
  icon: React.ReactNode;
}

const CROP_STEPS: StepItem[] = [
  {
    id: "geom",
    label: "AOI Boundary & Spatial Grid Setup",
    detail: "Validating coordinates, CRS projection, and field topology",
    sensor: "PostGIS / Shapely",
    icon: <Compass size={16} />,
  },
  {
    id: "s2",
    label: "Sentinel-2 Multi-Spectral Ingestion",
    detail: "Filtering cloud masks (SCL) and sampling 10m bands (B2, B3, B4, B8, B11)",
    sensor: "ESA Sentinel-2 L2A",
    icon: <Satellite size={16} />,
  },
  {
    id: "s1_bhoonidhi",
    label: "Sentinel-1 SAR & Bhoonidhi Ingestion",
    detail: "Querying ISRO Bhoonidhi STAC and extracting VV/VH backscatter",
    sensor: "ISRO / Sentinel-1 GRD",
    icon: <Radio size={16} />,
  },
  {
    id: "phenology",
    label: "Phenological Trajectory Analysis",
    detail: "Calculating NDVI, EVI, NDMI, NDRE curves & crop greenup slopes",
    sensor: "Spectral Physics Engine",
    icon: <Activity size={16} />,
  },
  {
    id: "classify",
    label: "Species Classification & Growth Stage",
    detail: "Fusing satellite evidence & computing Days Since Sowing (DSS)",
    sensor: "Random Forest & Ground Truth",
    icon: <Wheat size={16} />,
  },
];

const MOISTURE_STEPS: StepItem[] = [
  {
    id: "crop_context",
    label: "Crop Context & Stage Alignment",
    detail: "Aligning canopy architecture and baseline phenology",
    sensor: "Crop Stage Cache",
    icon: <Wheat size={16} />,
  },
  {
    id: "optical_indices",
    label: "Multi-Spectral Moisture Extraction",
    detail: "Computing NDMI canopy moisture, NDWI surface water & VCI vigor",
    sensor: "Sentinel-2 (10m)",
    icon: <Droplets size={16} />,
  },
  {
    id: "radar_dielectric",
    label: "Radar Dielectric & Roughness Analysis",
    detail: "Evaluating SAR cross-polarization backscatter ratio (VV/VH)",
    sensor: "Sentinel-1 SAR IW",
    icon: <Radio size={16} />,
  },
  {
    id: "thermal_lst",
    label: "Thermal Land Surface Temperature (LST)",
    detail: "Measuring thermal heat anomalies and surface stress indicators",
    sensor: "Landsat 8/9 Thermal Band 10",
    icon: <Thermometer size={16} />,
  },
  {
    id: "stress_map",
    label: "10m Pixel Stress Map Synthesis",
    detail: "Synthesizing composite stress score & spatial irrigation advisory",
    sensor: "Fused Moisture Engine",
    icon: <Layers size={16} />,
  },
];

export const AnalysisProgressCard: React.FC<AnalysisProgressCardProps> = ({
  type,
  fieldName,
}) => {
  const steps = type === "crop" ? CROP_STEPS : MOISTURE_STEPS;
  const [activeStepIndex, setActiveStepIndex] = useState(0);
  const [progress, setProgress] = useState(15);
  const [logs, setLogs] = useState<string[]>([
    "Connecting to Google Earth Engine & Bhoonidhi NRSC APIs...",
  ]);

  useEffect(() => {
    // Step progression timer
    const stepInterval = setInterval(() => {
      setActiveStepIndex((prev) => {
        if (prev < steps.length - 1) {
          const nextIndex = prev + 1;
          const nextStep = steps[nextIndex];
          setLogs((prevLogs) => [
            ...prevLogs.slice(-4),
            `[${new Date().toLocaleTimeString()}] > ${nextStep.label} (${nextStep.sensor})...`,
          ]);
          return nextIndex;
        }
        return prev;
      });
    }, 1800);

    // Smooth progress bar increment
    const progressInterval = setInterval(() => {
      setProgress((prev) => {
        if (prev < 92) {
          return prev + Math.floor(Math.random() * 4) + 2;
        }
        return prev;
      });
    }, 350);

    return () => {
      clearInterval(stepInterval);
      clearInterval(progressInterval);
    };
  }, [steps]);

  const title =
    type === "crop"
      ? "Analyzing Satellite Crop Classification"
      : "Analyzing Soil & Canopy Moisture Stress";

  const subtitle =
    type === "crop"
      ? "Synthesizing multi-temporal Sentinel-2 optical bands, Sentinel-1 SAR radar, and Bhoonidhi NRSC data..."
      : "Fusing NDMI leaf moisture, NDWI surface water, VCI vigor, SAR dielectric backscatter, and Landsat LST...";

  return (
    <div className="analysis-progress-card">
      {/* Top Banner with Radar Pulse */}
      <div className="analysis-progress-header">
        <div className="analysis-radar-orb">
          <div className="analysis-radar-pulse"></div>
          <div className="analysis-radar-ring ring-1"></div>
          <div className="analysis-radar-ring ring-2"></div>
          {type === "crop" ? (
            <Wheat className="analysis-orb-icon" size={24} />
          ) : (
            <Droplets className="analysis-orb-icon" size={24} />
          )}
        </div>

        <div className="analysis-header-text">
          <div className="analysis-badge-row">
            <span className="analysis-live-badge">
              <span className="live-dot"></span> LIVE SATELLITE ENGINE
            </span>
            {fieldName && <span className="analysis-field-badge">{fieldName}</span>}
          </div>
          <h3>{title}</h3>
          <p>{subtitle}</p>
        </div>

        <div className="analysis-percentage-badge">
          <span className="percentage-number">{Math.min(progress, 96)}%</span>
          <span className="percentage-label">Processing</span>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="analysis-bar-container">
        <div
          className="analysis-bar-fill"
          style={{ width: `${Math.min(progress, 96)}%` }}
        >
          <div className="analysis-bar-shimmer"></div>
        </div>
      </div>

      {/* Active Steps Tracker */}
      <div className="analysis-steps-list">
        {steps.map((step, idx) => {
          const isDone = idx < activeStepIndex;
          const isActive = idx === activeStepIndex;

          return (
            <div
              key={step.id}
              className={`analysis-step-item ${
                isDone ? "is-done" : isActive ? "is-active" : "is-pending"
              }`}
            >
              <div className="step-icon-wrap">
                {isDone ? (
                  <CheckCircle2 size={18} className="step-done-icon" />
                ) : isActive ? (
                  <Loader2 size={18} className="step-active-spinner" />
                ) : (
                  <div className="step-pending-dot"></div>
                )}
              </div>

              <div className="step-info">
                <div className="step-title-row">
                  <span className="step-label">{step.label}</span>
                  <span className="step-sensor-pill">{step.sensor}</span>
                </div>
                <span className="step-detail">{step.detail}</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Live Terminal Telemetry Output */}
      <div className="analysis-telemetry-box">
        <div className="telemetry-header">
          <Terminal size={14} />
          <span>Real-Time Engine Telemetry</span>
          <Sparkles size={12} className="telemetry-sparkle" />
        </div>
        <div className="telemetry-body">
          {logs.map((log, i) => (
            <div key={i} className="telemetry-line">
              {log}
            </div>
          ))}
          <div className="telemetry-cursor">_</div>
        </div>
      </div>
    </div>
  );
};
