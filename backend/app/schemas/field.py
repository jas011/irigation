from pydantic import BaseModel, Field as PydanticField
from typing import List, Literal, Optional, Dict, Any
from datetime import datetime

class GeoJSONPolygon(BaseModel):
    type: Literal["Polygon"]
    coordinates: List[List[List[float]]]  # Coordinates are [ [ [lng, lat], [lng, lat], ... ] ]

class GeoJSONFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    properties: Dict[str, Any] = PydanticField(default_factory=dict)
    geometry: GeoJSONPolygon

class CentroidResponse(BaseModel):
    latitude: float
    longitude: float

class LocationResponse(BaseModel):
    village: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None

class FieldValidationRequest(BaseModel):
    geometry: GeoJSONPolygon

class FieldValidationResponse(BaseModel):
    valid: bool
    geometry_valid: bool
    area_valid: bool
    area_m2: float
    area_hectares: float
    area_acres: float
    perimeter_m: float
    centroid: CentroidResponse
    location: LocationResponse
    geometry: GeoJSONPolygon
    message: str

class FieldCreateRequest(BaseModel):
    geometry: GeoJSONPolygon
    # Front-end provides the address if reverse geocoded, but backend will re-validate or fetch it if missing.
    location: Optional[LocationResponse] = None

class FieldResponse(BaseModel):
    id: int
    field_id: str
    user_id: int
    area_m2: float
    area_hectares: float
    area_acres: float
    perimeter_m: float
    latitude: float
    longitude: float
    village: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    geometry: Dict[str, Any]  # GeoJSON representation
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }


class FieldAIVerificationRequest(BaseModel):
    geometry: GeoJSONPolygon
    image_base64: Optional[str] = None


class FieldAIVerificationResponse(BaseModel):
    is_field: bool
    confidence: float
    land_type: str
    reason: str
    user_friendly_category: Optional[str] = None
    all_possibilities: Optional[Dict[str, float]] = None
    visual_features_observed: Optional[List[str]] = None
    details: Optional[Dict[str, Any]] = None


