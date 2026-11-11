import numpy as np
import logging
from typing import Dict, Any, List, Tuple
from datetime import datetime
from app.services.moisture.moisture_config import STRESS_THRESHOLDS, DEFAULT_WEIGHTS, WEIGHTS_WITH_LST, INDEX_BOUNDARIES
from app.utils.geometry import clipped_sample_cell
import os

logger = logging.getLogger("agrisense.moisture_stress")
MIN_MOISTURE_OBSERVATIONS = int(os.getenv("GEE_MOISTURE_MIN_S2_OBSERVATIONS", "3"))
STRESS_MAP_PIXELS = int(os.getenv("GEE_MOISTURE_MAP_MAX_PIXELS", "300"))

def calculate_index_stress(value: float, wet_limit: float, dry_limit: float) -> float:
    """
    Linearly maps an index value to a 0-100 stress score.
    Higher values represent more stress (dry).
    """
    if value is None or np.isnan(value):
        return 50.0 # default middle stress if missing
        
    # If wet is greater than dry (e.g. NDMI, NDWI, where higher is wetter)
    if wet_limit > dry_limit:
        if value >= wet_limit:
            return 0.0
        elif value <= dry_limit:
            return 100.0
        else:
            return float((wet_limit - value) / (wet_limit - dry_limit) * 100.0)
    else: # If dry is greater than wet (e.g. LST, where higher is hotter/drier)
        if value <= wet_limit:
            return 0.0
        elif value >= dry_limit:
            return 100.0
        else:
            return float((value - wet_limit) / (dry_limit - wet_limit) * 100.0)

def determine_stress_class(score: float) -> str:
    """
    Maps a 0-100 stress score to a categorical stress class.
    """
    if score < 20.0:
        return "No Stress"
    elif score < 40.0:
        return "Low Stress"
    elif score < 60.0:
        return "Moderate Stress"
    elif score < 80.0:
        return "High Stress"
    else:
        return "Severe Stress"

def calculate_stress_from_features(features: Dict[str, Any], has_lst: bool = False, has_s1: bool = False) -> Tuple[float, str, Dict[str, float]]:
    """
    Calculates the combined moisture stress score and breakdown using weights from config.
    """
    # 1. Normalize individual indices
    component_scores: Dict[str, float] = {}
    if features.get("latest_ndmi") is not None:
        component_scores["ndmi"] = calculate_index_stress(features["latest_ndmi"], INDEX_BOUNDARIES["ndmi"]["wet_limit"], INDEX_BOUNDARIES["ndmi"]["dry_limit"])
    if features.get("latest_ndwi") is not None:
        component_scores["ndwi"] = calculate_index_stress(features["latest_ndwi"], INDEX_BOUNDARIES["ndwi"]["wet_limit"], INDEX_BOUNDARIES["ndwi"]["dry_limit"])
    
    # Calculate VCI: Vegetation Condition Index
    # VCI = (NDVI - NDVI_min) / (NDVI_max - NDVI_min) * 100
    ndvi_max = features.get("ndvi_max")
    ndvi_min = features.get("ndvi_min")
    latest_ndvi = features.get("latest_ndvi")
    if None not in (ndvi_max, ndvi_min, latest_ndvi) and ndvi_max > ndvi_min:
        vci = (latest_ndvi - ndvi_min) / (ndvi_max - ndvi_min) * 100.0
        component_scores["vci"] = 100.0 - min(100.0, max(0.0, vci))
    else:
        vci = None
    
    # Calculate S1 SAR moisture stress proxy
    # In S1, higher VV/VH ratio or higher backscatter generally correlates with moisture.
    if has_s1 and features.get("latest_vv_vh_ratio") is not None:
        component_scores["sar"] = calculate_index_stress(features["latest_vv_vh_ratio"], 7.0, 3.5)
    
    # LST stress calculation if available
    lst_val = features.get("latest_lst")
    if has_lst and lst_val is not None:
        component_scores["lst"] = calculate_index_stress(
            lst_val,
            INDEX_BOUNDARIES["lst"]["cool_limit"],
            INDEX_BOUNDARIES["lst"]["hot_limit"]
        )
        weights = WEIGHTS_WITH_LST
    else:
        # Redistribute LST weight if Landsat is unavailable
        weights = DEFAULT_WEIGHTS
        
    # Only observed components participate. Renormalising prevents a missing
    # sensor from being replaced by an invented "typical" value.
    active_weights = {name: weights[name] for name in component_scores if name in weights}
    total_weight = sum(active_weights.values())
    if total_weight == 0:
        raise ValueError("No observed moisture indicators are available")
    score = sum(component_scores[name] * weight / total_weight for name, weight in active_weights.items())
        
    score = min(100.0, max(0.0, score))
    stress_class = determine_stress_class(score)
    
    breakdown = {f"{name}_stress": value for name, value in component_scores.items()}
    breakdown["observed_weight"] = total_weight
        
    return score, stress_class, breakdown

def get_pixel_level_stress(
    geometry_geojson: Dict[str, Any],
    s2_obs: List[Dict[str, Any]],
    start_date: str | None = None,
    end_date: str | None = None,
    has_lst: bool = False,
    latest_lst: float | None = None,
    has_s1: bool = False,
    latest_vv_vh_ratio: float | None = None,
) -> Dict[str, Any]:
    """
    Samples pixel-level points from the latest cloud-free Sentinel-2 image inside the field.
    Calculates moisture stress at 10m spatial resolution.
    Returns a GeoJSON FeatureCollection of points colored by stress class.
    """
    # Imports stay local so the deterministic scoring functions can be tested
    # without a live Earth Engine client.
    from app.services.gee.gee_service import gee_get_info, is_gee_ready
    import ee
    if not is_gee_ready() or not s2_obs:
        return {"type": "FeatureCollection", "features": []}
        
    geom = ee.Geometry(geometry_geojson)

    # Selecting the newest image in the field
    from app.services.gee.sentinel2_service import calculate_indices, mask_s2_clouds
    s2_col = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(geom)
    )
    if start_date and end_date:
        s2_col = s2_col.filterDate(start_date, end_date)
    s2_col = (
        s2_col.filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 80))
        .map(mask_s2_clouds)
        .map(calculate_indices)
        .sort('system:time_start', False)
    )

    try:
        latest_img = s2_col.first().select(['NDVI', 'NDMI', 'NDWI', 'EVI'])
    except Exception as exc:
        logger.warning("Unable to select a Sentinel-2 image for stress map: %s", exc)
        return {"type": "FeatureCollection", "features": []}
    
    # Sample points inside the boundary
    try:
        grid_points = gee_get_info(latest_img.sample(
            region=geom,
            scale=10,
            numPixels=STRESS_MAP_PIXELS,
            geometries=True,
            dropNulls=False,
            seed=42,
            tileScale=4
        ))
    except Exception as exc:
        logger.warning("Unable to sample Sentinel-2 stress map pixels: %s", exc)
        return {"type": "FeatureCollection", "features": []}
    
    features = []
    # Get overall field min/max NDVI for VCI calculation
    ndvi_max = max(obs['NDVI'] for obs in s2_obs)
    ndvi_min = min(obs['NDVI'] for obs in s2_obs)
    
    for feat in grid_points.get('features', []):
        coords = feat.get('geometry', {}).get('coordinates')
        props = feat.get('properties', {})
        
        if not coords or props.get('NDVI') is None:
            continue
            
        # Extract pixel indices
        p_ndvi = float(props.get('NDVI', 0.0))
        p_ndmi = float(props.get('NDMI', 0.0))
        p_ndwi = float(props.get('NDWI', 0.0))
        p_evi = float(props.get('EVI', 0.0))
        
        # Calculate pixel-level stress incorporating sensor fusion
        pixel_features = {
            "latest_ndvi": p_ndvi,
            "latest_ndmi": p_ndmi,
            "latest_ndwi": p_ndwi,
            "latest_evi": p_evi,
            "ndvi_max": ndvi_max,
            "ndvi_min": ndvi_min,
            "latest_lst": latest_lst,
            "latest_vv_vh_ratio": latest_vv_vh_ratio,
        }
        
        score, stress_class, _ = calculate_stress_from_features(
            pixel_features,
            has_lst=has_lst,
            has_s1=has_s1
        )
        
        cell_geometry = clipped_sample_cell(coords, geometry_geojson)
        if not cell_geometry:
            continue

        features.append({
            "type": "Feature",
            "geometry": cell_geometry,
            "properties": {
                "stress_score": score,
                "stress_class": stress_class
            }
        })
        
    return {
        "type": "FeatureCollection",
        "features": features
    }

def calculate_stress_trends(s2_obs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Computes historical stress scores over the observation period based on the Sentinel-2 time series.
    """
    if not s2_obs:
        return []
        
    ndvi_max = max(obs['NDVI'] for obs in s2_obs)
    ndvi_min = min(obs['NDVI'] for obs in s2_obs)
    
    trends = []
    for obs in s2_obs:
        features = {
            "latest_ndvi": obs['NDVI'],
            "latest_ndmi": obs['NDMI'],
            "latest_ndwi": obs['NDWI'],
            "latest_evi": obs['EVI'],
            "ndvi_max": ndvi_max,
            "ndvi_min": ndvi_min
        }
        score, stress_class, _ = calculate_stress_from_features(features)
        trends.append({
            "date": obs['date'],
            "stress_score": score,
            "stress_class": stress_class,
            "NDMI": obs['NDMI'],
            "NDVI": obs['NDVI']
        })
    return trends
