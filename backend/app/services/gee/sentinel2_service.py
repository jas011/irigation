import ee
import os
import json
import time
import hashlib
from datetime import datetime
from typing import Dict, Any, List
from app.services.gee.gee_service import gee_get_info, is_gee_ready, log_terminal

# Cloud Score+ configuration threshold (0.0 to 1.0, higher is stricter)
CLOUD_THRESHOLD = float(os.getenv("GEE_S2_CLOUD_SCORE_THRESHOLD", "0.60"))
MIN_VALID_COVERAGE_PCT = float(os.getenv("GEE_S2_MIN_VALID_COVERAGE_PCT", "20"))

# In-memory observation cache with TTL
_S2_CACHE: Dict[str, tuple[float, Dict[str, Any]]] = {}
CACHE_TTL_SECONDS = 600  # 10 minutes


def _get_cache_key(geometry_geojson: Dict[str, Any], start_date: str, end_date: str) -> str:
    geom_str = json.dumps(geometry_geojson, sort_keys=True)
    return hashlib.sha256(f"{geom_str}_{start_date}_{end_date}".encode()).hexdigest()


def mask_s2_clouds(image: ee.Image) -> ee.Image:
    """
    Masks clouds in a Sentinel-2 image using native Scene Classification Layer (SCL).
    0: NO_DATA, 1: SATURATED, 3: CLOUD_SHADOW, 8: CLOUD_MED, 9: CLOUD_HIGH, 10: CIRRUS, 11: SNOW
    """
    scl = image.select('SCL')
    invalid_scl = (
        scl.eq(0)
        .Or(scl.eq(1))
        .Or(scl.eq(3))
        .Or(scl.eq(8))
        .Or(scl.eq(9))
        .Or(scl.eq(10))
        .Or(scl.eq(11))
    )
    valid_bands = image.select('B8').mask().And(image.select('B11').mask())
    return image.updateMask(invalid_scl.Not().And(valid_bands))


def calculate_indices(image: ee.Image) -> ee.Image:
    """
    Calculates various vegetation and water indices for a Sentinel-2 image.
    """
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
    evi = image.expression(
        '2.5 * ((NIR - RED) / (NIR + 6.0 * RED - 7.5 * BLUE + 1.0))',
        {
            'NIR': image.select('B8').multiply(0.0001),
            'RED': image.select('B4').multiply(0.0001),
            'BLUE': image.select('B2').multiply(0.0001)
        }
    ).rename('EVI')
    ndwi = image.normalizedDifference(['B3', 'B8']).rename('NDWI')
    ndmi = image.normalizedDifference(['B8', 'B11']).rename('NDMI')
    ndre = image.normalizedDifference(['B8A', 'B5']).rename('NDRE')
    gndvi = image.normalizedDifference(['B8', 'B3']).rename('GNDVI')
    savi = image.expression(
        '((NIR - RED) / (NIR + RED + 0.5)) * 1.5',
        {
            'NIR': image.select('B8').multiply(0.0001),
            'RED': image.select('B4').multiply(0.0001)
        }
    ).rename('SAVI')
    return image.addBands(ndvi).addBands(evi).addBands(ndwi).addBands(ndmi).addBands(ndre).addBands(gndvi).addBands(savi)


def get_s2_time_series(geometry_geojson: Dict[str, Any], start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """
    Fetches the Sentinel-2 time series for the given geometry and date range.
    Returns a list of observations, each containing the date and mean index values.
    """
    return get_s2_time_series_with_metadata(geometry_geojson, start_date, end_date)["observations"]


def get_s2_time_series_with_metadata(
    geometry_geojson: Dict[str, Any], start_date: str, end_date: str
) -> Dict[str, Any]:
    """Return cloud-masked S2 observations, AOI coverage, and per-scene diagnostics with caching."""
    if not is_gee_ready():
        raise RuntimeError("Google Earth Engine is not initialized or authenticated.")

    cache_key = _get_cache_key(geometry_geojson, start_date, end_date)
    cached_entry = _S2_CACHE.get(cache_key)
    if cached_entry:
        timestamp, cached_result = cached_entry
        if time.time() - timestamp < CACHE_TTL_SECONDS:
            log_terminal("GEE Sentinel-2 (Cached)", f"Reused {len(cached_result['observations'])} observations for window {start_date} to {end_date}")
            return cached_result

    log_terminal("GEE Sentinel-2", f"Querying COPERNICUS/S2_SR_HARMONIZED for window {start_date} to {end_date}...")

    geom = ee.Geometry(geometry_geojson)
    s2_col = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(geom)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 95))
    )

    processed_col = s2_col.map(mask_s2_clouds).map(calculate_indices)

    def reduce_image(image: ee.Image) -> ee.Feature:
        date = image.date().format('YYYY-MM-dd')
        img_id = image.id()
        scene_cloud = image.get('CLOUDY_PIXEL_PERCENTAGE')
        
        # Calculate AOI-level spectral indices
        stats = image.select([
            'NDVI', 'EVI', 'NDMI', 'NDWI', 'NDRE', 'GNDVI', 'SAVI',
            'B2', 'B3', 'B4', 'B8', 'B11'
        ]).reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geom,
            scale=10,
            bestEffort=True,
            tileScale=2,
            maxPixels=1e9
        )
        
        # Measure AOI SCL histogram to accurately compute AOI cloud and valid pixel percentage
        scl_hist = image.select('SCL').reduceRegion(
            reducer=ee.Reducer.frequencyHistogram(),
            geometry=geom,
            scale=10,
            bestEffort=True,
            tileScale=2,
            maxPixels=1e9
        ).get('SCL')

        return ee.Feature(None, {
            'id': img_id,
            'date': date,
            'scene_cloud_pct': scene_cloud,
            'stats': stats,
            'scl_hist': scl_hist
        })

    batch_query = ee.Dictionary({
        "scene_count": s2_col.size(),
        "features": processed_col.map(reduce_image).toList(1000)
    })
    batch_res = gee_get_info(batch_query)
    scene_count = int(batch_res.get("scene_count", 0))
    if scene_count == 0:
        log_terminal("GEE Sentinel-2", f"0 scenes found in date range {start_date} to {end_date}.")
        diagnostics = {
            "sensor": "Sentinel-2",
            "found": 0,
            "accepted": 0,
            "rejected": 0,
            "rejection_reasons": ["No scenes intersecting AOI in selected date window"],
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
        scene_cloud = float(props.get('scene_cloud_pct', 0.0) or 0.0)
        stats = props.get('stats', {})
        scl_hist = props.get('scl_hist') or {}

        # Compute AOI valid pixels vs cloud pixels from SCL histogram
        total_aoi_pixels = sum(float(count) for count in scl_hist.values()) if scl_hist else 0.0
        # Invalid SCL: 0: NO_DATA, 1: SATURATED, 3: CLOUD_SHADOW, 8: CLOUD_MED, 9: CLOUD_HIGH, 10: CIRRUS, 11: SNOW
        cloud_pixels = sum(float(count) for val, count in scl_hist.items() if val in ("3", "8", "9", "10", "11"))
        aoi_cloud_pct = round((cloud_pixels / total_aoi_pixels * 100.0), 1) if total_aoi_pixels > 0 else 100.0
        aoi_valid_pct = round(100.0 - aoi_cloud_pct, 1)

        is_valid = bool(stats and stats.get('NDVI') is not None)

        if is_valid:
            rejection_reason = "Accepted"
            observations.append({
                'date': date,
                'NDVI': float(stats.get('NDVI')),
                'EVI': float(stats.get('EVI', 0.0)),
                'NDMI': float(stats.get('NDMI', 0.0)),
                'NDWI': float(stats.get('NDWI', 0.0)),
                'NDRE': float(stats.get('NDRE', 0.0)),
                'GNDVI': float(stats.get('GNDVI', 0.0)),
                'SAVI': float(stats.get('SAVI', 0.0)),
                'bands': {
                    'B2': stats.get('B2'),
                    'B3': stats.get('B3'),
                    'B4': stats.get('B4'),
                    'B5': stats.get('B5'),
                    'B6': stats.get('B6'),
                    'B7': stats.get('B7'),
                    'B8': stats.get('B8'),
                    'B8A': stats.get('B8A'),
                    'B11': stats.get('B11'),
                    'B12': stats.get('B12')
                }
            })
        else:
            if aoi_cloud_pct > 80.0:
                rejection_reason = f"AOI cloud/shadow obstruction ({aoi_cloud_pct:.1f}%)"
            elif total_aoi_pixels == 0:
                rejection_reason = "AOI outside raster footprint / no data"
            else:
                rejection_reason = f"Insufficient valid AOI pixels ({aoi_valid_pct:.1f}% valid)"
            rejection_reasons.append(rejection_reason)

        scene_diagnostics.append({
            "scene_id": img_id,
            "acquisition_date": date,
            "cloud_percentage": scene_cloud,
            "aoi_cloud_percentage": aoi_cloud_pct,
            "aoi_valid_pixel_percentage": aoi_valid_pct,
            "accepted": is_valid,
            "rejection_reason": rejection_reason
        })

    observations.sort(key=lambda x: x['date'])
    valid_count = len(observations)
    rejected_count = scene_count - valid_count

    # Summarize top rejection reasons
    from collections import Counter
    reason_counts = Counter(rejection_reasons)
    top_reasons = [f"{reason} (x{cnt})" for reason, cnt in reason_counts.most_common(3)]

    sensor_diagnostics = {
        "sensor": "Sentinel-2",
        "found": scene_count,
        "accepted": valid_count,
        "rejected": rejected_count,
        "main_rejection_reasons": top_reasons if top_reasons else ["None (all passed)"],
        "scene_diagnostics": scene_diagnostics
    }

    if observations:
        latest = observations[-1]
        log_terminal(
            "GEE Sentinel-2",
            f"Retrieved {scene_count} scenes -> {valid_count} valid cloud-free observations ({rejected_count} cloudy/invalid). "
            f"Latest ({latest['date']}): NDVI={latest['NDVI']:.3f}, NDMI={latest['NDMI']:.3f}, NDWI={latest['NDWI']:.3f}, EVI={latest['EVI']:.3f}"
        )
        result = {
            "observations": observations,
            "scene_count": scene_count,
            "valid_scene_count": valid_count,
            "valid_coverage_pct": 100.0,
            "sensor_diagnostics": sensor_diagnostics
        }
        _S2_CACHE[cache_key] = (time.time(), result)
        return result
    else:
        log_terminal("GEE Sentinel-2", f"Found {scene_count} scenes, but 0 passed cloud/quality filtering.")
        return {
            "observations": [],
            "scene_count": scene_count,
            "valid_scene_count": 0,
            "valid_coverage_pct": 0.0,
            "sensor_diagnostics": sensor_diagnostics
        }
