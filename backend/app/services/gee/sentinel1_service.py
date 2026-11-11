import ee
import os
import json
import time
import hashlib
from collections import Counter
from typing import Dict, Any, List
from app.services.gee.gee_service import gee_get_info, is_gee_ready, log_terminal

MIN_VALID_COVERAGE_PCT = float(os.getenv("GEE_S1_MIN_VALID_COVERAGE_PCT", "10"))

# In-memory S1 observation cache with TTL
_S1_CACHE: Dict[str, tuple[float, Dict[str, Any]]] = {}
CACHE_TTL_SECONDS = 600  # 10 minutes


def _get_s1_cache_key(geometry_geojson: Dict[str, Any], start_date: str, end_date: str) -> str:
    geom_str = json.dumps(geometry_geojson, sort_keys=True)
    return hashlib.sha256(f"s1_{geom_str}_{start_date}_{end_date}".encode()).hexdigest()


def calculate_s1_features(image: ee.Image) -> ee.Image:
    """
    Calculates SAR ratio and difference for Sentinel-1.
    Note: Sentinel-1 values in GRD are in decibels (dB).
    Linear ratio = 10^((VV - VH) / 10)
    dB difference = VV - VH
    """
    vv = image.select('VV')
    vh = image.select('VH')
    diff = vv.subtract(vh).rename('VV_VH_diff')
    ratio = image.expression(
        '10 ** ((VV - VH) / 10)',
        {
            'VV': vv,
            'VH': vh
        }
    ).rename('VV_VH_ratio')
    return image.addBands(diff).addBands(ratio)


def get_s1_time_series(geometry_geojson: Dict[str, Any], start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """
    Queries Sentinel-1 GRD SAR data for the geometry and time frame.
    Separates/normalizes ascending/descending orbits by calculating temporal statistics.
    Returns a list of S1 observations.
    """
    return get_s1_time_series_with_metadata(geometry_geojson, start_date, end_date)["observations"]


def get_s1_time_series_with_metadata(
    geometry_geojson: Dict[str, Any], start_date: str, end_date: str
) -> Dict[str, Any]:
    """Return S1 temporal features, AOI coverage, and per-scene diagnostics with caching and terminal logging."""
    if not is_gee_ready():
        raise RuntimeError("Google Earth Engine is not initialized or authenticated.")

    cache_key = _get_s1_cache_key(geometry_geojson, start_date, end_date)
    cached_entry = _S1_CACHE.get(cache_key)
    if cached_entry:
        timestamp, cached_result = cached_entry
        if time.time() - timestamp < CACHE_TTL_SECONDS:
            log_terminal("GEE Sentinel-1 (Cached)", f"Reused {len(cached_result['observations'])} SAR observations for window {start_date} to {end_date}")
            return cached_result

    log_terminal("GEE Sentinel-1", f"Querying COPERNICUS/S1_GRD IW (VV/VH) for window {start_date} to {end_date}...")

    geom = ee.Geometry(geometry_geojson)
    aoi_area = geom.area(1)
    
    s1_col = (ee.ImageCollection("COPERNICUS/S1_GRD")
              .filterBounds(geom).filterDate(start_date, end_date)
              .filter(ee.Filter.eq('instrumentMode', 'IW'))
              .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
              .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH')))

    processed_col = s1_col.map(calculate_s1_features)
    
    def reduce_image(image: ee.Image) -> ee.Feature:
        date = image.date().format('YYYY-MM-dd')
        img_id = image.id()
        orbit = image.get('orbitProperties_pass')
        
        # Calculate AOI SAR backscatter means
        stats = image.select(['VV', 'VH', 'VV_VH_ratio', 'VV_VH_diff']).reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geom,
            scale=10,
            bestEffort=True,
            tileScale=2,
            maxPixels=1e9
        )
        
        # Robust AOI footprint coverage percentage
        footprint = image.geometry()
        inter_area = footprint.intersection(geom, 1).area(1)
        coverage_pct = inter_area.divide(aoi_area).multiply(100.0)

        return ee.Feature(None, {
            'id': img_id,
            'date': date,
            'orbit': orbit,
            'stats': stats,
            'coverage_pct': coverage_pct
        })
        
    batch_query = ee.Dictionary({
        "scene_count": s1_col.size(),
        "features": processed_col.map(reduce_image).toList(1000)
    })
    batch_res = gee_get_info(batch_query)
    scene_count = int(batch_res.get("scene_count", 0))
    if scene_count == 0:
        log_terminal("GEE Sentinel-1", f"0 SAR scenes found in date range {start_date} to {end_date}.")
        diagnostics = {
            "sensor": "Sentinel-1",
            "found": 0,
            "accepted": 0,
            "rejected": 0,
            "main_rejection_reasons": ["No SAR scenes intersecting AOI in selected date window"],
            "scene_diagnostics": []
        }
        return {
            "observations": [],
            "scene_count": 0,
            "valid_scene_count": 0,
            "valid_coverage_pct": 0.0,
            "sensor_diagnostics": diagnostics
        }

    raw_features = batch_res.get("features", [])
    observations = []
    scene_diagnostics = []
    rejection_reasons = []

    for feat in raw_features:
        props = feat.get('properties', {})
        date = props.get('date')
        img_id = props.get('id', 'unknown')
        orbit = props.get('orbit')
        stats = props.get('stats', {})
        coverage_pct = float(props.get('coverage_pct', 0.0) or 0.0)
        
        is_valid = bool(stats and stats.get('VV') is not None and coverage_pct >= MIN_VALID_COVERAGE_PCT)

        if is_valid:
            rejection_reason = "Accepted"
            observations.append({
                'date': date,
                'orbit': orbit,
                'VV': float(stats.get('VV')),
                'VH': float(stats.get('VH')),
                'VV_VH_ratio': float(stats.get('VV_VH_ratio', 1.0)),
                'VV_VH_diff': float(stats.get('VV_VH_diff', 0.0)),
                'coverage_pct': round(coverage_pct, 1)
            })
        else:
            if coverage_pct < MIN_VALID_COVERAGE_PCT:
                rejection_reason = f"Insufficient AOI coverage ({coverage_pct:.1f}% < {MIN_VALID_COVERAGE_PCT:.0f}%)"
            else:
                rejection_reason = "Null / unreadable backscatter values in AOI"
            rejection_reasons.append(rejection_reason)

        scene_diagnostics.append({
            "scene_id": img_id,
            "acquisition_date": date,
            "orbit": orbit,
            "coverage_percentage": round(coverage_pct, 1),
            "required_threshold": MIN_VALID_COVERAGE_PCT,
            "accepted": is_valid,
            "rejection_reason": rejection_reason
        })
            
    observations.sort(key=lambda x: x['date'])
    valid_count = len(observations)
    rejected_count = scene_count - valid_count

    reason_counts = Counter(rejection_reasons)
    top_reasons = [f"{reason} (x{cnt})" for reason, cnt in reason_counts.most_common(3)]

    sensor_diagnostics = {
        "sensor": "Sentinel-1",
        "found": scene_count,
        "accepted": valid_count,
        "rejected": rejected_count,
        "main_rejection_reasons": top_reasons if top_reasons else ["None (all passed)"],
        "scene_diagnostics": scene_diagnostics
    }

    if observations:
        latest = observations[-1]
        log_terminal(
            "GEE Sentinel-1",
            f"Retrieved {scene_count} SAR scenes -> {valid_count} valid observations ({rejected_count} rejected). "
            f"Latest ({latest['date']}): VV={latest['VV']:.1f} dB, VH={latest['VH']:.1f} dB, Ratio={latest['VV_VH_ratio']:.2f}"
        )
        result = {
            "observations": observations,
            "scene_count": scene_count,
            "valid_scene_count": valid_count,
            "valid_coverage_pct": 100.0,
            "sensor_diagnostics": sensor_diagnostics
        }
        _S1_CACHE[cache_key] = (time.time(), result)
        return result
    else:
        log_terminal("GEE Sentinel-1", f"Found {scene_count} SAR scenes, but 0 passed coverage/quality filtering.")
        return {
            "observations": [],
            "scene_count": scene_count,
            "valid_scene_count": 0,
            "valid_coverage_pct": 0.0,
            "sensor_diagnostics": sensor_diagnostics
        }
