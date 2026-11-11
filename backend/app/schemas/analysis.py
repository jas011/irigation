from pydantic import BaseModel
from typing import Dict, Any, List, Optional

class CropClassifyRequest(BaseModel):
    field_id: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    mode: Optional[str] = "current_season"

class CropClassifyResponse(BaseModel):
    field_id: str
    crop: Optional[str] = None
    confidence: Optional[float] = None
    all_probabilities: Dict[str, float]
    indices: Dict[str, float]
    time_series: List[Dict[str, Any]]
    growth_stage: str = "N/A"
    growth_stage_confidence: Optional[float] = None
    sowing_date: Optional[str] = None
    days_since_sowing: Optional[int] = None
    classification_map: Dict[str, Any]
    data_quality: str
    classification_status: str
    message: Optional[str] = None
    availability: Dict[str, Any] = {}
    class_distribution: Dict[str, float] = {}
    legend_classes: List[str] = []
    validation_accuracy: Optional[float] = None
    validation_metrics: Optional[Dict[str, Any]] = None

class MoistureAnalyzeRequest(BaseModel):
    field_id: str
    crop: str
    growth_stage: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class MoistureAnalyzeResponse(BaseModel):
    field_id: str
    stress_level: str
    stress_score: float
    stress_map: Dict[str, Any]
    indicators: Dict[str, float]
    stress_time_series: List[Dict[str, Any]]
    data_quality: str
