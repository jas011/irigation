import React from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from "recharts";
import {
  Calendar,
  Database,
  Sprout
} from "lucide-react";
import { useFieldContext } from "../../layouts/DashboardLayout";
import ResultMap from "../../components/Dashboard/ResultMap";
import "../Dashboard.css";

interface CropDataProps {
  data: {
    crop: string | null;
    confidence: number | null;
    all_probabilities: Record<string, number>;
    indices: Record<string, number>;
    time_series: Array<{
      date: string;
      NDVI: number;
      EVI: number;
      NDMI: number;
      NDWI: number;
      SAVI?: number;
      GNDVI?: number;
    }>;
    growth_stage: string;
    growth_stage_confidence: number | null;
    sowing_date?: string | null;
    days_since_sowing?: number | null;
    classification_map: any;
    data_quality: string;
    classification_status?: string;
    message?: string;
    legend_classes?: string[];
    availability?: {
      decision_policy?: string;
    };
  };
}

const CropClassification: React.FC<CropDataProps> = ({ data }) => {
  const { setMapOverlayMode, setCropGrid, selectedFieldData } = useFieldContext();
  const confidence = data.confidence ?? 0;
  const hasClassification = Boolean(data.crop) && data.classification_status !== "unavailable";
  const hasClassificationMap = Boolean(data.classification_map?.features?.length);

  React.useEffect(() => {
    if (hasClassificationMap) {
      setCropGrid(data.classification_map);
      setMapOverlayMode("crop");
    }
  }, [hasClassificationMap, data.classification_map, setCropGrid, setMapOverlayMode]);

  const getCropDisplay = (crop: string | null) => {
    if (!crop) return "Unavailable";
    if (crop === "Paddy") return "Paddy (Rice)";
    return crop;
  };

  const formatPercentage = (val: number) => {
    return `${(val * 100).toFixed(0)}%`;
  };

  // Derived indicators
  const ndvi = data.indices?.NDVI || 0;
  const greenCover = Math.min(99, Math.max(0, ndvi * 100));
  const lai = Math.max(0, ndvi * 3.5);
  const fapar = Math.max(0, ndvi * 0.95);

  return (
    <div className="crop-classification-section">
      
      {/* Title */}
      <div className="dashboard-section-header">
        <h2 className="dashboard-section-title">
          <Sprout color="#66ff00" size={36} />
          <span>AI Crop Classification & Growth Stage</span>
        </h2>
        <p className="dashboard-section-subtitle">
          Satellite-driven land cover analytics and phenology signatures.
        </p>
      </div>

      <div className="dashboard-grid-container-3col">
        
        {/* Card 1: Detected Crop */}
        <div className="info-card info-card-large detected-crop-card">
          <div className="detected-crop-header-shell">
            <span className="detected-crop-title">Detected Crop</span>
          </div>

          <div className="detected-crop-content">
            <h3 className="detected-crop-value">{getCropDisplay(data.crop)}</h3>

            <div className="detected-crop-metric">
              <div
                className="detected-crop-gauge"
                style={{
                  ['--progress' as any]: `${confidence * 100}`
                }}
              >
                <div className="detected-crop-gauge-inner">
                  <span>{hasClassification ? formatPercentage(confidence) : "N/A"}</span>
                </div>
              </div>
            </div>

            <div className="detected-crop-description">
              {data.message || data.availability?.decision_policy || "Model Confidence score. Validation accuracy is currently unavailable for this custom field."}
            </div>
          </div>
        </div>

        {/* Spatial classification output with direct overlay */}
        <ResultMap
          geometry={selectedFieldData?.geometry}
          overlay={hasClassificationMap ? data.classification_map : null}
          mode="crop"
          crop={data.crop}
        />

        {/* Card 2: Growth Stage */}
        <div className="info-card info-card-large growth-stage-card">
          <div className="growth-stage-header-shell">
            <span className="growth-stage-title">Growth Stage</span>
          </div>

          <div className="growth-stage-content">
            <h3 className="growth-stage-value">{data.growth_stage}</h3>

            <div className="growth-stage-info">
              <div className="growth-stage-item">
                <span className="growth-stage-item-label">Sowing Date:</span>
                <div className="growth-stage-item-value">
                  <Calendar size={14} color="var(--primary-green)" />
                  <span>{data.sowing_date || "—"}</span>
                </div>
              </div>
              <div className="growth-stage-item">
                <span className="growth-stage-item-label">Age (DSS):</span>
                <div className="growth-stage-item-value">
                  <Database size={14} color="var(--primary-green)" />
                  <span>{data.days_since_sowing != null ? `${data.days_since_sowing} days` : "—"}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

      </div>

      {/* Row 2: Vegetation Indices & NDVI Chart */}
      <div className="dashboard-grid-container-2col">
        
        {/* NDVI Time Series Chart */}
        <div className="chart-container">
          <h3 className="chart-title">Interactive NDVI Time Series</h3>
          <div className="chart-wrapper">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data.time_series}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="date" fontSize={11} tickLine={false} />
                <YAxis domain={[0, 1.0]} fontSize={11} tickLine={false} />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="NDVI"
                  stroke="var(--primary-green)"
                  strokeWidth={3}
                  activeDot={{ r: 6 }}
                  dot={{ r: 3 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Spectral Index cards */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
          
          <div className="spectral-index-card">
            <span className="spectral-index-label">NDVI</span>
            <span className="spectral-index-value spectral-index-value-green">
              {ndvi.toFixed(3)}
            </span>
          </div>

          <div className="spectral-index-card">
            <span className="spectral-index-label">EVI</span>
            <span className="spectral-index-value">
              {(data.indices?.EVI || 0).toFixed(3)}
            </span>
          </div>

          <div className="spectral-index-card">
            <span className="spectral-index-label">NDMI</span>
            <span className="spectral-index-value">
              {(data.indices?.NDMI || 0).toFixed(3)}
            </span>
          </div>

          <div className="spectral-index-card">
            <span className="spectral-index-label">NDWI</span>
            <span className="spectral-index-value">
              {(data.indices?.NDWI || 0).toFixed(3)}
            </span>
          </div>

          <div className="spectral-index-card spectral-full-width">
            <span className="spectral-index-label">Data Quality</span>
            <span className={`spectral-index-value ${data.data_quality === "Good" ? "data-quality-good" : "data-quality-warning"}`}>
              {data.data_quality} ({data.time_series?.length} Observations)
            </span>
          </div>

        </div>

      </div>

      {/* Other Field Insights */}
      <div className="biophysical-estimations">
        <h3 className="biophysical-title">Derived Biophysical Estimations</h3>
        <div className="biophysical-grid">
          
          <div className="biophysical-item">
            <span className="biophysical-label">Fractional Green Cover</span>
            <strong className="biophysical-value">{greenCover.toFixed(1)}%</strong>
          </div>

          <div className="biophysical-item">
            <span className="biophysical-label">Leaf Area Index (LAI)</span>
            <strong className="biophysical-value">{lai.toFixed(2)} m²/m²</strong>
          </div>

          <div className="biophysical-item">
            <span className="biophysical-label">FAPAR</span>
            <strong className="biophysical-value">{fapar.toFixed(2)}</strong>
          </div>

        </div>
      </div>

    </div>
  );
};

export default CropClassification;
