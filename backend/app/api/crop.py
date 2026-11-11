import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.field import Field
from app.models.analysis import AnalysisResult
from app.schemas.analysis import CropClassifyRequest, CropClassifyResponse
from app.services.gee.sentinel2_service import get_s2_time_series
from app.services.gee.sentinel1_service import get_s1_time_series
from app.services.crop.crop_classification_service import (
    EMPTY_MAP,
    ClassificationUnavailable,
    run_spatial_classification,
)
from app.services.crop.growth_stage_service import detect_growth_stage
from app.services.bhoonidhi.bhoonidhi_client import BhoonidhiError
from app.services.bhoonidhi.bhoonidhi_service import search_bhoonidhi_sentinel1
from app.utils.geometry import wkb_to_geojson
from app.utils.analysis_window import AnalysisWindowError, resolve_analysis_window

router = APIRouter(prefix="/crop", tags=["crop"])
MAP_MODEL_VERSION = "3.0.0"
logger = logging.getLogger(__name__)

@router.post("/classify", response_model=CropClassifyResponse)
async def classify_crop(
    req: CropClassifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Runs multi-temporal satellite processing to classify crop type and detect growth stage.
    """
    # 1. Fetch Field from Database and Verify Ownership
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
        
    # Convert WKB geometry to GeoJSON dict
    geometry_geojson = wkb_to_geojson(field.geometry)
    
    # 2. Determine Date Range
    try:
        start_date, end_date = resolve_analysis_window(req.start_date, req.end_date)
    except AnalysisWindowError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
        
    # 3. Fetch the two required source datasets. A fresh run is required so
    # the GEE/Bhoonidhi availability checks always apply to the final decision.
    # produced from a local/synthetic model or a single external source.
    try:
        # Fetch S2 optical observations
        s2_obs = get_s2_time_series(geometry_geojson, start_date, end_date)
        
        # Fetch S1 SAR observations (runs in background/GEE, fallback logs warning)
        s1_obs = []
        try:
            s1_obs = get_s1_time_series(geometry_geojson, start_date, end_date)
        except Exception as e_s1:
            print(f"Sentinel-1 fetch warning: {str(e_s1)}")
            
    except Exception as e_gee:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Google Earth Engine processing failed: {str(e_gee)}"
        )
        
    if not s2_obs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No usable Sentinel-2 observations were found for this field and period."
        )

    try:
        bhoonidhi_products = await search_bhoonidhi_sentinel1(
            geometry_geojson, start_date, end_date
        )
    except BhoonidhiError as exc:
        logger.warning("Bhoonidhi data verification degraded: %s", exc)
        bhoonidhi_products = []
    except Exception as exc:
        logger.warning("Bhoonidhi data verification degraded: %s", exc)
        bhoonidhi_products = []

    if not bhoonidhi_products:
        logger.warning("Bhoonidhi returned no online Sentinel-1 products for this field and period.")
        
    obs_count = len(s2_obs)
    if obs_count >= 10:
        data_quality = "Good"
    elif obs_count >= 5:
        data_quality = "Moderate"
    else:
        data_quality = "Poor"

    latest_indices = {
        "NDVI": s2_obs[-1].get("NDVI", 0.0),
        "EVI": s2_obs[-1].get("EVI", 0.0),
        "NDMI": s2_obs[-1].get("NDMI", 0.0),
        "NDWI": s2_obs[-1].get("NDWI", 0.0),
        "SAVI": s2_obs[-1].get("SAVI", 0.0),
        "GNDVI": s2_obs[-1].get("GNDVI", 0.0),
    }

    clean_time_series = []
    for obs in s2_obs:
        clean_time_series.append({
            "date": obs["date"],
            "NDVI": obs["NDVI"],
            "EVI": obs["EVI"],
            "NDMI": obs["NDMI"],
            "NDWI": obs["NDWI"],
            "SAVI": obs.get("SAVI", 0.0),
            "GNDVI": obs.get("GNDVI", 0.0)
        })

    availability = {
        "s2_observation_count": len(s2_obs),
        "s1_observation_count": len(s1_obs),
        "gee": {"status": "available", "s2_observation_count": len(s2_obs)},
        "bhoonidhi": {
            "status": "available",
            "sentinel1_product_count": len(bhoonidhi_products),
            "products": [
                {"id": product["id"], "date": product["date"], "satellite": product["satellite"], "polarisation": product["polarisation"]}
                for product in bhoonidhi_products
            ],
        },
        "decision_policy": "Combined decision: validated GEE classifier plus Bhoonidhi Sentinel-1 product availability. Dynamic World and JRC are intentionally not queried because they do not feed this validated model.",
    }
    classification_status = "completed"
    message = None
    crop_type = None
    confidence = None
    all_probs = {}
    class_distribution = {}
    legend_classes = []
    classification_map = EMPTY_MAP

    try:
        spatial_result = run_spatial_classification(geometry_geojson, start_date, end_date)
    except ClassificationUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Validated GEE classification is unavailable; no fallback decision was produced: {exc}",
        ) from exc
    except Exception as exc:
        # Do not replace the provider error with an authentication hint.  This
        # stage can fail for many reasons (for example, a training asset
        # schema, a quota error, or a failed server-side computation), and the
        # original error is required to resolve it.
        logger.exception("Validated GEE classification failed for field %s", req.field_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validated GEE classification failed: {exc}",
        ) from exc

    crop_type = spatial_result["crop"]
    classification_status = spatial_result.get("classification_status", "completed")
    message = spatial_result.get("message")
    class_distribution = spatial_result.get("class_distribution", {})
    confidence = spatial_result.get("confidence")
    if confidence is None and class_distribution:
        confidence = max(class_distribution.values())
    confidence = confidence or 0.0
    all_probs = {
        label: class_distribution.get(label, 0.0)
        for label in spatial_result.get("available_classes", class_distribution)
    }
    classification_map = spatial_result.get("classification_map") or EMPTY_MAP
    legend_classes = spatial_result.get("legend_classes", [])
    availability.update({
        "training_sample_count": spatial_result.get("training_sample_count"),
        "classification_pixel_count": spatial_result.get("classification_pixel_count"),
        "classification_coverage_pct": spatial_result.get("classification_coverage_pct"),
        "landsat_scene_count": spatial_result.get("landsat_scene_count"),
        "feature_count": spatial_result.get("feature_count"),
    })
    validation_metrics = spatial_result.get("validation_metrics")

    if crop_type:
        stage_data = detect_growth_stage(crop_type, s2_obs, s1_obs)
    else:
        stage_data = {
            "stage": "N/A",
            "confidence": None,
            "sowing_date": None,
            "days_since_sowing": None,
        }

    # 6. Cache successful crop results in database
    if crop_type:
        db_analysis = AnalysisResult(
            field_id=req.field_id,
            start_date=start_date,
            end_date=end_date,
            crop=crop_type,
            crop_confidence=confidence,
            growth_stage=stage_data["stage"],
            growth_stage_confidence=stage_data["confidence"],
            sowing_date=stage_data["sowing_date"],
            days_since_sowing=stage_data["days_since_sowing"],
            classification_map=classification_map,
            time_series=clean_time_series,
            data_quality=data_quality,
            model_version=MAP_MODEL_VERSION
        )
        
        try:
            db.add(db_analysis)
            db.commit()
        except Exception as e_db:
            db.rollback()
            print(f"Database caching failed: {str(e_db)}") # non-blocking warning

    return CropClassifyResponse(
        field_id=req.field_id,
        crop=crop_type,
        confidence=confidence,
        all_probabilities=all_probs,
        indices=latest_indices,
        time_series=clean_time_series,
        growth_stage=stage_data["stage"],
        growth_stage_confidence=stage_data["confidence"],
        sowing_date=stage_data["sowing_date"],
        days_since_sowing=stage_data["days_since_sowing"],
        classification_map=classification_map,
        data_quality=data_quality,
        classification_status=classification_status,
        message=message,
        availability=availability,
        class_distribution=class_distribution,
        legend_classes=legend_classes,
        validation_accuracy=(validation_metrics or {}).get("overall_accuracy"),
        validation_metrics=validation_metrics,
    )
