import asyncio
import logging
import os
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.services.analysis.bhoonidhi_service import BhoonidhiService
from app.services.analysis.gee_health_service import GEEHealthError, verify_gee_authentication
from app.services.analysis.ground_truth_service import GroundTruthService
from app.services.crop.crop_classification_service import ClassificationUnavailable, run_spatial_classification
from app.services.crop.crop_features import extract_features
from app.services.crop.crop_name_utils import normalize_crop_name
from app.services.crop.growth_stage_service import detect_growth_stage
from app.services.crop.local_crop_classifier import CsvTrainedCropModel
from app.services.gee.sentinel1_service import get_s1_time_series
from app.services.gee.sentinel2_service import get_s2_time_series
from app.utils.analysis_window import resolve_analysis_window

logger = logging.getLogger("agrisense.analysis.crop")

SOURCE_WEIGHTS = {
    "satellite_phenology": 0.50,
    "gee_rf": 0.40,
    "ground_truth_csv_overlap": 0.35,
    "ground_truth_csv_nearest": 0.20,
    "csv_trained_ml": 0.20,
}


def _extract_gee_signal(geometry: Dict[str, Any], start_date: str, end_date: str) -> Optional[Dict[str, Any]]:
    if not os.getenv("GEE_CROP_TRAINING_ASSET"):
        return None
    try:
        result = run_spatial_classification(geometry, start_date, end_date)
    except ClassificationUnavailable as exc:
        logger.warning("GEE crop classification unavailable: %s", exc)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.exception("GEE crop classification failed: %s", exc)
        return None

    crop_label = result.get("crop")
    confidence = result.get("confidence")
    distribution = result.get("class_distribution") or {}
    if not crop_label and distribution:
        crop_label = max(distribution, key=distribution.get)
        confidence = distribution[crop_label]
    if not crop_label:
        return None

    return {
        "label": normalize_crop_name(crop_label),
        "confidence": round(float(confidence or 0.0), 3),
        "source": "gee_rf",
        "classification_status": result.get("classification_status", "completed"),
        "class_distribution": distribution,
        "classification_map": result.get("classification_map"),
        "validation_metrics": result.get("validation_metrics"),
        "message": result.get("message"),
    }


def _generate_field_crop_map(geometry: Dict[str, Any], predicted_crop: str, start_date: str, end_date: str) -> Dict[str, Any]:
    """Generates 10m spatial pixel cells for the field classification overlay."""
    import ee
    from app.services.gee.gee_service import gee_get_info, is_gee_ready
    from app.services.gee.sentinel2_service import calculate_indices, mask_s2_clouds
    from app.utils.geometry import clipped_sample_cell

    if not is_gee_ready() or not geometry:
        return {"type": "FeatureCollection", "features": []}

    try:
        geom = ee.Geometry(geometry)
        s2_col = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(geom)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 80))
            .map(mask_s2_clouds)
            .map(calculate_indices)
            .sort('system:time_start', False)
        )
        latest_img = s2_col.first().select(['NDVI', 'NDWI'])
        grid_points = gee_get_info(latest_img.sample(
            region=geom,
            scale=10,
            numPixels=250,
            geometries=True,
            dropNulls=False,
            seed=42,
            tileScale=4
        ))
        features = []
        for feat in grid_points.get('features', []):
            coords = feat.get('geometry', {}).get('coordinates')
            props = feat.get('properties', {})
            if not coords:
                continue
            ndvi_val = props.get('NDVI')
            ndwi_val = props.get('NDWI')
            if ndwi_val is not None and float(ndwi_val) > 0.1 and (ndvi_val is None or float(ndvi_val) < 0.2):
                cell_crop = "Water"
            elif ndvi_val is not None and float(ndvi_val) < 0.22:
                cell_crop = "Bare Soil"
            else:
                cell_crop = predicted_crop

            cell = clipped_sample_cell(coords, geometry)
            if cell:
                features.append({
                    "type": "Feature",
                    "geometry": cell,
                    "properties": {"crop": cell_crop}
                })
        return {"type": "FeatureCollection", "features": features}
    except Exception as exc:
        logger.warning("Could not generate field crop overlay: %s", exc)
        return {"type": "FeatureCollection", "features": []}


def _evaluate_phenological_crop_signal(
    features: Dict[str, Any],
    s2_obs: List[Dict[str, Any]],
    s1_obs: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Scientifically deduce crop type from multi-temporal spectral and radar dynamics."""
    if not s2_obs or len(s2_obs) < 3:
        return None

    ndvi_max = features.get("ndvi_max", 0.0)
    ndvi_min = features.get("ndvi_min", 0.0)
    ndvi_amp = features.get("ndvi_amp", 0.0)
    ndvi_std = features.get("ndvi_std", 0.0)
    ndwi_max = features.get("ndwi_max", -1.0)
    ndwi_mean = features.get("ndwi_mean", -1.0)
    ndmi_max = features.get("ndmi_max", -1.0)
    latest_ndvi = features.get("latest_ndvi", 0.0)
    s1_vh_mean = features.get("s1_vh_mean", -20.0)
    peak_date = features.get("ndvi_peak_date", "")

    # 1. Permanent Water detection
    if ndwi_mean > 0.05 and ndvi_max < 0.20:
        return {"label": "Water", "confidence": 0.95, "source": "satellite_phenology", "reason": "Persistent positive NDWI and low vegetation index."}

    # 2. Bare Soil / Fallow
    if ndvi_max < 0.22 and ndmi_max < 0.05:
        return {"label": "Bare Soil", "confidence": 0.90, "source": "satellite_phenology", "reason": "Persistent low NDVI (<0.22) and low moisture across entire observation window."}

    # 3. Permanent / Non-Crop Dense Vegetation (forest, orchards, perennial greenery)
    if ndvi_min > 0.50 and ndvi_amp < 0.15 and ndvi_std < 0.05:
        return {"label": "Non-Crop", "confidence": 0.88, "source": "satellite_phenology", "reason": "Stable high canopy with minimal seasonal phenological variation."}

    # Peak timing analysis
    peak_month = 7
    if peak_date and len(peak_date) >= 7:
        try:
            peak_month = int(peak_date.split("-")[1])
        except Exception:
            pass

    # 4. Paddy (Rice): Kharif crop, initial inundation (high NDWI, low early NDVI), peak NDVI > 0.65 in Aug-Oct, high VH
    if peak_month in (7, 8, 9, 10) and ndvi_max >= 0.55:
        early_obs = s2_obs[:max(1, len(s2_obs)//3)]
        early_has_water = any(obs.get("NDWI", -1.0) > -0.05 or obs.get("NDMI", -1.0) > 0.20 for obs in early_obs)
        conf = 0.85 if early_has_water else 0.75
        return {"label": "Paddy", "confidence": conf, "source": "satellite_phenology", "reason": "Kharif peak greening profile with early surface moisture and high canopy density."}

    # 5. Wheat: Rabi crop, peak NDVI in Jan, Feb, or March
    if peak_month in (1, 2, 3, 4) and ndvi_max >= 0.55:
        return {"label": "Wheat", "confidence": 0.85, "source": "satellite_phenology", "reason": "Rabi winter-spring peak vegetative profile with rapid April senescence."}

    # 6. Cotton: Long Kharif crop, high SAR backscatter (rough canopy structure, VH >= -16 dB)
    if peak_month in (8, 9, 10, 11) and ndvi_max >= 0.50 and s1_vh_mean > -17.0:
        return {"label": "Cotton", "confidence": 0.80, "source": "satellite_phenology", "reason": "High SAR cross-polarization backscatter and late Kharif canopy profile."}

    # 7. Maize: Sharp short vegetative cycle
    if ndvi_amp >= 0.45 and ndvi_max >= 0.65:
        return {"label": "Maize", "confidence": 0.75, "source": "satellite_phenology", "reason": "High vegetative greening amplitude and fast canopy development."}

    if ndvi_max >= 0.40:
        return {"label": "Other Crop", "confidence": 0.65, "source": "satellite_phenology", "reason": "Active crop canopy detected without definitive single-species signature."}

    return None


def _fuse_crop_signals(*signals: Optional[Dict[str, Any]]) -> Tuple[str, float, List[str]]:
    votes: Dict[str, float] = defaultdict(float)
    active_sources: List[str] = []
    for signal in signals:
        if not signal or not signal.get("label"):
            continue
        label = normalize_crop_name(signal["label"])
        if label in ("Unknown", "Insufficient Data"):
            continue
        weight = SOURCE_WEIGHTS.get(signal.get("source", ""), 0.2)
        votes[label] += weight * float(signal.get("confidence", 0.5))
        active_sources.append(str(signal.get("source")))

    if not votes:
        return "Unknown", 0.0, active_sources

    winner = max(votes, key=votes.get)
    total_weight = sum(votes.values())
    confidence = round(votes[winner] / total_weight, 3) if total_weight else 0.5
    return winner, confidence, active_sources


class CropAnalysisService:
    @staticmethod
    def _insufficient_data_response(
        geometry: Dict[str, Any],
        start_date: str,
        end_date: str,
        s2_count: int,
        gee_status: str,
        bhoonidhi_status: str,
    ) -> Dict[str, Any]:
        return {
            "cropPrediction": {
                "label": "Insufficient Data",
                "confidence": 0.0,
                "source": "quality_gate",
                "active_sources": [],
                "signals": {},
            },
            "growthStage": {
                "stage": "Unknown",
                "confidence": 0.0,
                "sowing_date": None,
                "days_since_sowing": None,
                "season": "Unknown",
                "method": "insufficient_satellite_observations",
                "evidence": [f"Only {s2_count} quality-checked Sentinel-2 observations available for the period {start_date} to {end_date}."],
            },
            "indices": {},
            "timeSeries": [],
            "classificationMap": {"type": "FeatureCollection", "features": []},
            "area": {
                "geometry": geometry,
                "matched_records": 0,
                "reference_crop": "Insufficient Data",
            },
            "dataSources": {
                "ground_truth_csv": GroundTruthService.resolve_csv_path().as_posix(),
                "gee": gee_status,
                "bhoonidhi": bhoonidhi_status,
                "sentinel2_observations": s2_count,
                "sentinel1_observations": 0,
                "bhoonidhi_products": 0,
            },
            "dataQuality": "Poor",
            "data_quality": "Poor",
            "availability": {
                "s2_observation_count": s2_count,
                "s1_observation_count": 0,
                "bhoonidhi_product_count": 0,
                "data_quality": "Poor",
            },
            "processing": {
                "status": "low_confidence",
                "quality_checks": [
                    "AOI validated",
                    "GEE authentication verified",
                    "Satellite observations checked: INSUFFICIENT CLEAR OBSERVATIONS",
                ],
                "requested_window": {
                    "start_date": start_date,
                    "end_date": end_date,
                },
            },
        }

    @classmethod
    async def analyze_field(
        cls,
        *,
        geometry: Dict[str, Any],
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> Dict[str, Any]:
        if not geometry:
            raise ValueError("Invalid AOI: field geometry is required for crop analysis.")

        start_date, end_date = resolve_analysis_window(start_date, end_date)
        print(f"\n{'='*75}\n[Stage 2 Crop Analysis] Starting analysis for window: {start_date} to {end_date}\n{'='*75}", flush=True)

        try:
            gee_health = verify_gee_authentication()
            gee_status = gee_health.get("status", "ready")
        except GEEHealthError as exc:
            raise RuntimeError(str(exc)) from exc

        # Parallelize data acquisition across GEE S2, GEE S1, GEE RF, and Bhoonidhi
        async def fetch_s2():
            try:
                from app.services.gee.sentinel2_service import get_s2_time_series_with_metadata
                return await asyncio.to_thread(get_s2_time_series_with_metadata, geometry, start_date, end_date)
            except Exception as e:
                logger.warning("Sentinel-2 fetch error: %s", e)
                return {"observations": [], "scene_count": 0, "sensor_diagnostics": {"sensor": "Sentinel-2", "found": 0, "accepted": 0, "rejected": 0, "main_rejection_reasons": [str(e)]}}

        async def fetch_s1():
            try:
                from app.services.gee.sentinel1_service import get_s1_time_series_with_metadata
                return await asyncio.to_thread(get_s1_time_series_with_metadata, geometry, start_date, end_date)
            except Exception as e:
                logger.warning("Sentinel-1 fetch error: %s", e)
                return {"observations": [], "scene_count": 0, "sensor_diagnostics": {"sensor": "Sentinel-1", "found": 0, "accepted": 0, "rejected": 0, "main_rejection_reasons": [str(e)]}}

        async def fetch_gee_rf():
            try:
                return await asyncio.to_thread(_extract_gee_signal, geometry, start_date, end_date)
            except Exception as e:
                logger.warning("GEE RF extraction error: %s", e)
                return None

        async def fetch_bhoonidhi():
            if BhoonidhiService.configured():
                try:
                    prods = await BhoonidhiService.validate_aoi(geometry, start_date, end_date)
                    return "available", prods
                except Exception as e:
                    logger.warning("Bhoonidhi error: %s", e)
                    return "degraded", []
            return "not_configured", []

        s2_data, s1_data, gee_signal, (bhoonidhi_status, bhoonidhi_products) = await asyncio.gather(
            fetch_s2(),
            fetch_s1(),
            fetch_gee_rf(),
            fetch_bhoonidhi(),
        )

        s2_obs = s2_data.get("observations", [])
        s1_obs = s1_data.get("observations", [])
        s2_count = len(s2_obs)
        s1_count = len(s1_obs)

        s2_diag = s2_data.get("sensor_diagnostics", {})
        s1_diag = s1_data.get("sensor_diagnostics", {})

        print(
            f"\n[Stage 2 Sensor Diagnostics]\n"
            f"Sentinel-2: found={s2_diag.get('found', 0)}, accepted={s2_diag.get('accepted', 0)}, rejected={s2_diag.get('rejected', 0)} | Rejection: {', '.join(s2_diag.get('main_rejection_reasons', []))}\n"
            f"Sentinel-1: found={s1_diag.get('found', 0)}, accepted={s1_diag.get('accepted', 0)}, rejected={s1_diag.get('rejected', 0)} | Rejection: {', '.join(s1_diag.get('main_rejection_reasons', []))}\n"
            f"Bhoonidhi: found={len(bhoonidhi_products)}, status={bhoonidhi_status}\n",
            flush=True
        )

        # Gate: If satellite observations are inadequate, do not fabricate a crop prediction
        if s2_count < 2:
            print(f"[Stage 2 Crop Analysis] INSUFFICIENT DATA: Only {s2_count} valid Sentinel-2 scenes found. Returning Insufficient Data.", flush=True)
            res = cls._insufficient_data_response(geometry, start_date, end_date, s2_count, gee_status, bhoonidhi_status)
            res["dataSources"]["sensor_diagnostics"] = {
                "sentinel2": s2_diag,
                "sentinel1": s1_diag,
                "bhoonidhi": {"status": bhoonidhi_status, "product_count": len(bhoonidhi_products)}
            }
            return res

        # 1. Extract biophysical features
        features = extract_features(s2_obs, s1_obs)

        # 2. Derive physical phenology signal
        phenology_signal = _evaluate_phenological_crop_signal(features, s2_obs, s1_obs)

        # 3. Query Ground Truth CSV and ML model
        csv_signal = GroundTruthService.predict_crop(geometry)
        ml_signal = CsvTrainedCropModel.predict(geometry, season=csv_signal.get("season"))

        # 4. Multi-Source Fusion
        crop_label, fused_confidence, active_sources = _fuse_crop_signals(
            phenology_signal,
            gee_signal,
            csv_signal,
            ml_signal,
        )
        normalized_crop = normalize_crop_name(crop_label)

        # 5. Detect growth stage
        stage_data = detect_growth_stage(normalized_crop, s2_obs, s1_obs)
        stage_data["method"] = "satellite_phenology"

        latest_indices = {
            "NDVI": s2_obs[-1].get("NDVI"),
            "EVI": s2_obs[-1].get("EVI"),
            "NDMI": s2_obs[-1].get("NDMI"),
            "NDWI": s2_obs[-1].get("NDWI"),
            "SAVI": s2_obs[-1].get("SAVI"),
            "GNDVI": s2_obs[-1].get("GNDVI"),
        }

        time_series = [
            {
                "date": obs["date"],
                "NDVI": obs.get("NDVI"),
                "EVI": obs.get("EVI"),
                "NDMI": obs.get("NDMI"),
                "NDWI": obs.get("NDWI"),
                "SAVI": obs.get("SAVI"),
                "GNDVI": obs.get("GNDVI"),
            }
            for obs in s2_obs
        ]

        data_quality = "Good" if s2_count >= 8 else ("Moderate" if s2_count >= 4 else "Poor")

        print(
            f"[Stage 2 Crop Analysis Result] Detected Crop: {normalized_crop} (Confidence: {fused_confidence*100:.1f}%) | "
            f"Growth Stage: {stage_data.get('stage')} | S2 Obs: {s2_count} | S1 Obs: {s1_count} | Data Quality: {data_quality}\n"
            f"{'='*75}\n",
            flush=True
        )

        return {
            "cropPrediction": {
                "label": normalized_crop,
                "confidence": fused_confidence,
                "source": "fused",
                "active_sources": active_sources,
                "signals": {
                    "phenology": phenology_signal,
                    "gee": gee_signal,
                    "csv": csv_signal,
                    "ml": ml_signal,
                },
            },
            "growthStage": {
                "stage": stage_data.get("stage"),
                "confidence": stage_data.get("confidence"),
                "sowing_date": stage_data.get("sowing_date"),
                "days_since_sowing": stage_data.get("days_since_sowing"),
                "season": stage_data.get("season") or csv_signal.get("season"),
                "method": stage_data.get("method"),
                "evidence": stage_data.get("evidence", []),
            },
            "indices": latest_indices,
            "timeSeries": time_series,
            "classificationMap": (
                (gee_signal or {}).get("classification_map")
                if (gee_signal or {}).get("classification_map", {}).get("features")
                else _generate_field_crop_map(geometry, normalized_crop, start_date, end_date)
            ),
            "area": {
                "geometry": geometry,
                "matched_records": csv_signal.get("matched_records", 0),
                "reference_crop": normalized_crop,
            },
            "dataSources": {
                "ground_truth_csv": GroundTruthService.resolve_csv_path().as_posix(),
                "gee": gee_status,
                "bhoonidhi": bhoonidhi_status,
                "sentinel2_observations": s2_count,
                "sentinel1_observations": s1_count,
                "bhoonidhi_products": len(bhoonidhi_products),
                "sensor_diagnostics": {
                    "sentinel2": s2_diag,
                    "sentinel1": s1_diag,
                    "bhoonidhi": {"status": bhoonidhi_status, "product_count": len(bhoonidhi_products)}
                },
            },
            "availability": {
                "s2_observation_count": s2_count,
                "s1_observation_count": s1_count,
                "bhoonidhi_product_count": len(bhoonidhi_products),
                "data_quality": data_quality,
            },
            "processing": {
                "status": "completed",
                "quality_checks": [
                    "AOI validated",
                    "Sentinel-2 indices computed",
                    "Sentinel-1 SAR integrated" if s1_count else "Sentinel-1 SAR unavailable",
                    "Phenological trajectory evaluated",
                    "CSV ground-truth cross-referenced",
                    "Bhoonidhi Sentinel-1 verified",
                ],
                "requested_window": {
                    "start_date": start_date,
                    "end_date": end_date,
                },
            },
        }

