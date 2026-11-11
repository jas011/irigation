import ee
import os
import json
import time
import hashlib
from collections import Counter
from typing import Dict, Any, List
from app.services.gee.gee_service import gee_get_info, is_gee_ready, log_terminal

_LANDSAT_CACHE: Dict[str, tuple[float, Dict[str, Any]]] = {}
CACHE_TTL_SECONDS = 600  # 10 minutes


def _get_landsat_cache_key(geometry_geojson: Dict[str, Any], start_date: str, end_date: str) -> str:
    geom_str = json.dumps(geometry_geojson, sort_keys=True)
    return hashlib.sha256(f"lst_{geom_str}_{start_date}_{end_date}".encode()).hexdigest()


def mask_landsat_sr(image: ee.Image) -> ee.Image:
    """
    Cloud mask for Landsat 8/9 Level-2 Surface Reflectance/Temperature.
    Bit 3 = Cloud, Bit 4 = Cloud Shadow
    """
    qa = image.select('QA_PIXEL')
    cloud_shadow_mask = qa.bitwiseAnd(1 << 4).eq(0)
    cloud_mask = qa.bitwiseAnd(1 << 3).eq(0)
    mask = cloud_shadow_mask.And(cloud_mask)
    return image.updateMask(mask)


def calculate_lst(image: ee.Image) -> ee.Image:
    """
    Converts Landsat 8/9 Band 10 (ST_B10) to Land Surface Temperature (LST) in Celsius.
    Digital Number (DN) scaling: value * 0.00341802 + 149.0 (in Kelvin)
    Celsius = Kelvin - 273.15
    """
    st_b10 = image.select('ST_B10')
    lst = st_b10.multiply(0.00341802).add(149.0).subtract(273.15).rename('LST')
    return image.addBands(lst)


def get_landsat_lst_time_series(geometry_geojson: Dict[str, Any], start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """
    Fetches the Landsat 8 and Landsat 9 Land Surface Temperature time series.
    Returns list of observations.
    """
    return get_landsat_lst_time_series_with_metadata(geometry_geojson, start_date, end_date)["observations"]


def get_landsat_lst_time_series_with_metadata(
    geometry_geojson: Dict[str, Any], start_date: str, end_date: str
) -> Dict[str, Any]:
    """
    Fetches Landsat 8/9 LST time series with caching, full per-scene diagnostics, and terminal logging.
    """
    if not is_gee_ready():
        raise RuntimeError("Google Earth Engine is not initialized or authenticated.")

    cache_key = _get_landsat_cache_key(geometry_geojson, start_date, end_date)
    cached_entry = _LANDSAT_CACHE.get(cache_key)
    if cached_entry:
        timestamp, cached_result = cached_entry
        if time.time() - timestamp < CACHE_TTL_SECONDS:
            log_terminal("GEE Landsat LST (Cached)", f"Reused {len(cached_result['observations'])} LST observations for window {start_date} to {end_date}")
            return cached_result

    log_terminal("GEE Landsat LST", f"Querying Landsat 8/9 L2 Thermal Surface Temperature for window {start_date} to {end_date}...")

    geom = ee.Geometry(geometry_geojson)
    
    l8_col = (
        ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
        .filterBounds(geom)
        .filterDate(start_date, end_date)
        .map(mask_landsat_sr)
        .map(calculate_lst)
    )
    
    l9_col = (
        ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")
        .filterBounds(geom)
        .filterDate(start_date, end_date)
        .map(mask_landsat_sr)
        .map(calculate_lst)
    )
    
    merged_col = l8_col.merge(l9_col)

    def reduce_image(image: ee.Image) -> ee.Feature:
        date = image.date().format('YYYY-MM-dd')
        img_id = image.id()
        means = image.select(['LST', 'QA_PIXEL']).reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geom,
            scale=30,
            bestEffort=True,
            tileScale=2,
            maxPixels=1e9
        )
        return ee.Feature(None, {
            'id': img_id,
            'date': date,
            'LST': means.get('LST'),
            'QA_PIXEL': means.get('QA_PIXEL')
        })

    batch_query = ee.Dictionary({
        "scene_count": merged_col.size(),
        "features": merged_col.map(reduce_image).toList(1000)
    })
    batch_res = gee_get_info(batch_query)
    scene_count = int(batch_res.get("scene_count", 0))
    if scene_count == 0:
        log_terminal("GEE Landsat LST", f"0 Landsat scenes found in date range {start_date} to {end_date}.")
        diagnostics = {
            "sensor": "Landsat",
            "found": 0,
            "accepted": 0,
            "rejected": 0,
            "main_rejection_reasons": ["No Landsat scenes intersecting AOI in selected date window"],
            "scene_diagnostics": []
        }
        res = {
            "observations": [],
            "scene_count": 0,
            "valid_scene_count": 0,
            "sensor_diagnostics": diagnostics
        }
        _LANDSAT_CACHE[cache_key] = (time.time(), res)
        return res

    raw_features = batch_res.get("features", [])
    observations = []
    scene_diagnostics = []
    rejection_reasons = []

    for feat in raw_features:
        props = feat.get('properties', {})
        date = props.get('date')
        img_id = props.get('id', 'unknown')
        lst_val = props.get('LST')
        qa_pixel = props.get('QA_PIXEL')
        
        is_valid = lst_val is not None

        if is_valid:
            rejection_reason = "Accepted"
            observations.append({
                'date': date,
                'LST': float(lst_val),
                'QA_PIXEL': qa_pixel
            })
        else:
            rejection_reason = "Masked by QA_PIXEL (cloud / cloud-shadow over AOI)"
            rejection_reasons.append(rejection_reason)

        scene_diagnostics.append({
            "scene_id": img_id,
            "acquisition_date": date,
            "lst_celsius": round(float(lst_val), 2) if is_valid else None,
            "qa_pixel": qa_pixel,
            "accepted": is_valid,
            "rejection_reason": rejection_reason
        })
            
    observations.sort(key=lambda x: x['date'])
    valid_count = len(observations)
    rejected_count = scene_count - valid_count

    reason_counts = Counter(rejection_reasons)
    top_reasons = [f"{reason} (x{cnt})" for reason, cnt in reason_counts.most_common(3)]

    sensor_diagnostics = {
        "sensor": "Landsat",
        "found": scene_count,
        "accepted": valid_count,
        "rejected": rejected_count,
        "main_rejection_reasons": top_reasons if top_reasons else ["None (all passed)"],
        "scene_diagnostics": scene_diagnostics
    }

    if observations:
        latest = observations[-1]
        log_terminal(
            "GEE Landsat LST",
            f"Retrieved {scene_count} Landsat scenes -> {valid_count} valid LST observations ({rejected_count} cloud-masked). "
            f"Latest ({latest['date']}): {latest['LST']:.1f}°C"
        )
    else:
        log_terminal("GEE Landsat LST", f"Found {scene_count} Landsat scenes, but 0 valid LST measurements after cloud masking.")

    result = {
        "observations": observations,
        "scene_count": scene_count,
        "valid_scene_count": valid_count,
        "sensor_diagnostics": sensor_diagnostics
    }
    _LANDSAT_CACHE[cache_key] = (time.time(), result)
    return result
