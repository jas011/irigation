from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.field import Field
from app.models.analysis import AnalysisResult
from app.schemas.analysis import MoistureAnalyzeRequest, MoistureAnalyzeResponse
from app.services.gee.sentinel2_service import get_s2_time_series
from app.services.gee.sentinel1_service import get_s1_time_series
from app.services.gee.landsat_service import get_landsat_lst_time_series
from app.services.crop.crop_features import extract_features
from app.services.moisture.moisture_stress_service import (
    calculate_stress_from_features, 
    get_pixel_level_stress, 
    calculate_stress_trends
)
from app.utils.geometry import wkb_to_geojson
from app.utils.analysis_window import AnalysisWindowError, resolve_analysis_window
from app.services.moisture.moisture_stress_service import MIN_MOISTURE_OBSERVATIONS

router = APIRouter(prefix="/moisture", tags=["moisture"])
MAP_MODEL_VERSION = "1.1.0"

@router.post("/analyze", response_model=MoistureAnalyzeResponse)
async def analyze_moisture(
    req: MoistureAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Computes moisture stress mapping, indicators, and trends for the confirmed field.
    """
    # 1. Fetch Field and verify ownership
    field = db.query(Field).filter(Field.field_id == req.field_id).first()
    if not field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Field with ID {req.field_id} not found."
        )
        
    if field.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to analyze this field."
        )
        
    geometry_geojson = wkb_to_geojson(field.geometry)
    
    # 2. Date Range Setup
    try:
        start_date, end_date = resolve_analysis_window(req.start_date, req.end_date)
    except AnalysisWindowError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
        
    # 3. Check Cache
    cached_result = db.query(AnalysisResult).filter(
        AnalysisResult.field_id == req.field_id,
        AnalysisResult.start_date == start_date,
        AnalysisResult.end_date == end_date
    ).order_by(AnalysisResult.created_at.desc()).first()
    
    if cached_result and cached_result.stress_score is not None and cached_result.model_version == MAP_MODEL_VERSION:
        # Load indices from time_series if available
        time_series = cached_result.time_series or []
        latest = time_series[-1] if time_series else {}
        # Cached analyses preserve observed optical values only. Never present
        # an inferred VCI or invented SAR values as a satellite measurement.
        indicators = {key.lower(): value for key, value in latest.items()
                      if key in {"NDVI", "NDMI", "NDWI", "EVI"} and value is not None}
        
        return MoistureAnalyzeResponse(
            field_id=cached_result.field_id,
            stress_level=cached_result.stress_class,
            stress_score=cached_result.stress_score,
            stress_map=cached_result.stress_map or {"type": "FeatureCollection", "features": []},
            indicators=indicators,
            stress_time_series=cached_result.stress_time_series or [],
            data_quality=cached_result.data_quality
        )
        
    # 4. Fetch GEE Data
    try:
        s2_obs = get_s2_time_series(geometry_geojson, start_date, end_date)
        
        s1_obs = []
        try:
            s1_obs = get_s1_time_series(geometry_geojson, start_date, end_date)
        except Exception:
            pass
            
        # Fetch Landsat Surface Temperature
        lst_obs = []
        has_lst = False
        try:
            lst_obs = get_landsat_lst_time_series(geometry_geojson, start_date, end_date)
            if lst_obs:
                has_lst = True
        except Exception as e_lst:
            print(f"Landsat LST warning: {str(e_lst)}")
            
    except Exception as e_gee:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Google Earth Engine processing failed: {str(e_gee)}"
        )
        
    if len(s2_obs) < MIN_MOISTURE_OBSERVATIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Moisture analysis requires at least {MIN_MOISTURE_OBSERVATIONS} quality-controlled Sentinel-2 observations."
        )
        
    # 5. Extract features
    features = extract_features(s2_obs, s1_obs)
    
    # Add LST details if present
    if has_lst and lst_obs:
        features["latest_lst"] = lst_obs[-1]["LST"]
        
    # 6. Calculate Stress Model
    score, stress_class, breakdown = calculate_stress_from_features(
        features, 
        has_lst=has_lst, 
        has_s1=bool(s1_obs)
    )
    
    # 7. Spatial Stress Map (10m grid)
    stress_map = get_pixel_level_stress(geometry_geojson, s2_obs, start_date, end_date)
    
    # 8. Stress Trend time series
    stress_trends = calculate_stress_trends(s2_obs)
    
    # 9. Quality Evaluation
    obs_count = len(s2_obs)
    data_quality = "Good" if obs_count >= 10 else ("Moderate" if obs_count >= 5 else "Poor")
    
    # 10. Persist results in cache
    # Update existing record if it was created by classification endpoint
    if cached_result:
        cached_result.stress_score = score
        cached_result.stress_class = stress_class
        cached_result.stress_map = stress_map
        cached_result.stress_time_series = stress_trends
        cached_result.model_version = MAP_MODEL_VERSION
    else:
        # Create fresh result
        cached_result = AnalysisResult(
            field_id=req.field_id,
            start_date=start_date,
            end_date=end_date,
            crop=req.crop,
            crop_confidence=0.80, # default placeholder
            growth_stage=req.growth_stage,
            growth_stage_confidence=0.80,
            stress_score=score,
            stress_class=stress_class,
            stress_map=stress_map,
            stress_time_series=stress_trends,
            data_quality=data_quality,
            model_version=MAP_MODEL_VERSION
        )
        db.add(cached_result)
        
    try:
        db.commit()
    except Exception as e_db:
        db.rollback()
        print(f"Database caching failed: {str(e_db)}")
        
    # Prepare indicator averages for display
    latest_ndvi = s2_obs[-1].get("NDVI")
    latest_ndmi = s2_obs[-1].get("NDMI")
    latest_ndwi = s2_obs[-1].get("NDWI")
    
    indicators_res = {
        "ndmi": latest_ndmi,
        "ndwi": latest_ndwi,
        "vci": 100.0 - breakdown.get("vci_stress", 50.0),
    }
    if s1_obs:
        indicators_res["sar_vv"] = s1_obs[-1].get("VV")
        indicators_res["sar_vh"] = s1_obs[-1].get("VH")
    if has_lst and lst_obs:
        indicators_res["lst"] = lst_obs[-1]["LST"]
        
    return MoistureAnalyzeResponse(
        field_id=req.field_id,
        stress_level=stress_class,
        stress_score=score,
        stress_map=stress_map,
        indicators=indicators_res,
        stress_time_series=stress_trends,
        data_quality=data_quality
    )
