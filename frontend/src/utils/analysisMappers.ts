export function mapCropAnalysisToClassificationData(response: any) {
  const mlProbabilities = response?.cropPrediction?.signals?.ml?.probabilities || {};
  const geeDistribution = response?.cropPrediction?.signals?.gee?.class_distribution || {};
  const allProbabilities: Record<string, number> = { ...mlProbabilities, ...geeDistribution };

  if (!Object.keys(allProbabilities).length && response?.cropPrediction?.label) {
    allProbabilities[response.cropPrediction.label] = response.cropPrediction.confidence ?? 0;
  }

  const legendClasses = Object.keys(geeDistribution).length
    ? Object.keys(geeDistribution)
    : Object.keys(allProbabilities);

  const activeSources = response?.cropPrediction?.active_sources || [];
  const decisionPolicy = activeSources.length
    ? "Crop identified by comparing field reference samples with satellite vegetation, moisture, and radar patterns, then cross-checking the result against independent regional observations."
    : "Crop identification is based on satellite vegetation and moisture patterns, supported by field reference data.";

  return {
    crop: response?.cropPrediction?.label ?? null,
    confidence: response?.cropPrediction?.confidence ?? null,
    all_probabilities: allProbabilities,
    indices: response?.indices ?? {},
    time_series: response?.timeSeries ?? [],
    growth_stage: response?.growthStage?.stage ?? "N/A",
    growth_stage_confidence: response?.growthStage?.confidence ?? null,
    sowing_date: response?.growthStage?.sowing_date ?? null,
    days_since_sowing: response?.growthStage?.days_since_sowing ?? null,
    classification_map: response?.classificationMap ?? { type: "FeatureCollection", features: [] },
    data_quality: response?.availability?.data_quality ?? "Poor",
    classification_status: response?.processing?.status === "completed" ? "completed" : "unavailable",
    message: response?.cropPrediction?.signals?.gee?.message || undefined,
    legend_classes: legendClasses,
    availability: {
      decision_policy: decisionPolicy,
    },
  };
}

export function mapMoistureAnalysisToStressData(response: any, fieldId: string) {
  return {
    field_id: fieldId,
    stress_level: response?.stressLevel ?? "Moderate Stress",
    stress_score: response?.stressScore ?? 0,
    stress_map: response?.stressMap ?? { type: "FeatureCollection", features: [] },
    indicators: response?.indicators ?? {},
    stress_time_series: response?.stressTimeSeries ?? [],
    data_quality: response?.dataQuality ?? "Poor",
  };
}
