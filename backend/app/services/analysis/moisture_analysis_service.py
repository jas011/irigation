import asyncio
import logging
from typing import Any, Dict, List

from app.services.analysis.gee_health_service import GEEHealthError, verify_gee_authentication
from app.services.crop.crop_features import extract_features
from app.services.crop.crop_name_utils import normalize_crop_name
from app.services.gee.landsat_service import get_landsat_lst_time_series
from app.services.gee.sentinel1_service import get_s1_time_series
from app.services.gee.sentinel2_service import get_s2_time_series
from app.services.moisture.moisture_stress_service import (
    MIN_MOISTURE_OBSERVATIONS,
    calculate_stress_from_features,
    calculate_stress_trends,
    get_pixel_level_stress,
)
from app.utils.analysis_window import resolve_analysis_window

logger = logging.getLogger("agrisense.analysis.moisture")


class MoistureAnalysisService:
    @classmethod
    async def analyze_field(
        cls,
        *,
        geometry: Dict[str, Any],
        crop_prediction: str,
        growth_stage: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> Dict[str, Any]:
        if not geometry:
            raise ValueError("Invalid AOI: field geometry is required for moisture analysis.")
        if not crop_prediction:
            raise ValueError("Crop prediction is required before moisture analysis.")

        start_date, end_date = resolve_analysis_window(start_date, end_date)
        print(f"\n{'='*75}\n[Stage 3 Moisture Stress Analysis] Starting analysis for window: {start_date} to {end_date} (Crop: {crop_prediction})\n{'='*75}", flush=True)

        try:
            gee_health = verify_gee_authentication()
            gee_status = gee_health.get("status", "ready")
        except GEEHealthError as exc:
            raise RuntimeError(str(exc)) from exc

        # Parallel fetch across Sentinel-2, Sentinel-1, and Landsat LST
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

        async def fetch_lst():
            try:
                from app.services.gee.landsat_service import get_landsat_lst_time_series_with_metadata
                return await asyncio.to_thread(get_landsat_lst_time_series_with_metadata, geometry, start_date, end_date)
            except Exception as e:
                logger.warning("Landsat LST fetch error: %s", e)
                return {"observations": [], "scene_count": 0, "sensor_diagnostics": {"sensor": "Landsat", "found": 0, "accepted": 0, "rejected": 0, "main_rejection_reasons": [str(e)]}}

        s2_data, s1_data, lst_data = await asyncio.gather(
            fetch_s2(),
            fetch_s1(),
            fetch_lst(),
        )

        s2_obs = s2_data.get("observations", [])
        s1_obs = s1_data.get("observations", [])
        lst_obs = lst_data.get("observations", [])
        has_lst = bool(lst_obs)
        obs_count = len(s2_obs)

        s2_diag = s2_data.get("sensor_diagnostics", {})
        s1_diag = s1_data.get("sensor_diagnostics", {})
        lst_diag = lst_data.get("sensor_diagnostics", {})

        print(
            f"\n[Stage 3 Sensor Diagnostics]\n"
            f"Sentinel-2: found={s2_diag.get('found', 0)}, accepted={s2_diag.get('accepted', 0)}, rejected={s2_diag.get('rejected', 0)} | Rejection: {', '.join(s2_diag.get('main_rejection_reasons', []))}\n"
            f"Sentinel-1: found={s1_diag.get('found', 0)}, accepted={s1_diag.get('accepted', 0)}, rejected={s1_diag.get('rejected', 0)} | Rejection: {', '.join(s1_diag.get('main_rejection_reasons', []))}\n"
            f"Landsat: found={lst_diag.get('found', 0)}, accepted={lst_diag.get('accepted', 0)}, rejected={lst_diag.get('rejected', 0)} | Rejection: {', '.join(lst_diag.get('main_rejection_reasons', []))}\n",
            flush=True
        )

        if obs_count < 1:
            print(f"[Stage 3 Moisture Stress] INSUFFICIENT DATA: 0 quality-controlled Sentinel-2 observations available for {start_date} to {end_date}.", flush=True)
            return {
                "field_id": None,
                "stressLevel": "Insufficient Data",
                "stressScore": 0.0,
                "confidence": 0.0,
                "crop": normalize_crop_name(crop_prediction),
                "growthStage": growth_stage,
                "indicators": {
                    "ndmi": None,
                    "ndwi": None,
                    "ndvi": None,
                    "vci": 0.0,
                },
                "stressMap": {"type": "FeatureCollection", "features": []},
                "stressTimeSeries": [],
                "dataQuality": "Poor",
                "dataSources": {
                    "gee": gee_status,
                    "sentinel2_observations": 0,
                    "sentinel1_observations": len(s1_obs),
                    "landsat_observations": len(lst_obs),
                    "sensor_diagnostics": {
                        "sentinel2": s2_diag,
                        "sentinel1": s1_diag,
                        "landsat": lst_diag,
                    }
                },
                "processing": {
                    "status": "insufficient_data",
                    "quality_checks": [
                        "AOI validated",
                        "GEE authentication verified",
                        "Satellite observations checked: INSUFFICIENT CLEAR OBSERVATIONS",
                    ],
                    "requested_window": {
                        "start_date": start_date,
                        "end_date": end_date,
                    },
                    "breakdown": {},
                },
            }

        features = extract_features(s2_obs, s1_obs)
        if has_lst and lst_obs:
            features["latest_lst"] = lst_obs[-1]["LST"]

        score, stress_class, breakdown = calculate_stress_from_features(
            features,
            has_lst=has_lst,
            has_s1=bool(s1_obs),
        )

        # Generate 10m pixel-level spatial stress map and historical trends
        stress_map = get_pixel_level_stress(
            geometry,
            s2_obs,
            start_date,
            end_date,
            has_lst=has_lst,
            latest_lst=features.get("latest_lst"),
            has_s1=bool(s1_obs),
            latest_vv_vh_ratio=features.get("latest_vv_vh_ratio"),
        )
        stress_trends = calculate_stress_trends(s2_obs)

        data_quality = "Good" if obs_count >= 8 else ("Moderate" if obs_count >= 4 else "Poor")

        latest_ndvi = s2_obs[-1].get("NDVI")
        latest_ndmi = s2_obs[-1].get("NDMI")
        latest_ndwi = s2_obs[-1].get("NDWI")
        indicators = {
            "ndmi": latest_ndmi,
            "ndwi": latest_ndwi,
            "ndvi": latest_ndvi,
            "vci": round(100.0 - breakdown.get("vci_stress", 50.0), 1),
        }
        if s1_obs:
            indicators["sar_vv"] = s1_obs[-1].get("VV")
            indicators["sar_vh"] = s1_obs[-1].get("VH")
        if has_lst and lst_obs:
            indicators["lst"] = lst_obs[-1]["LST"]

        normalized_crop = normalize_crop_name(crop_prediction)
        lst_str = f"{lst_obs[-1]['LST']:.1f}°C" if has_lst and lst_obs else "Unavailable"
        sar_str = "Available" if s1_obs else "Unavailable"

        print(
            f"[Stage 3 Moisture Result] Condition: {stress_class} (Score: {score:.1f}/100) | "
            f"NDMI: {latest_ndmi:.3f} | NDWI: {latest_ndwi:.3f} | VCI: {indicators['vci']}% | "
            f"SAR: {sar_str} | LST: {lst_str} | "
            f"Data Quality: {data_quality}\n"
            f"{'='*75}\n",
            flush=True
        )

        return {
            "field_id": None,
            "stressLevel": stress_class,
            "stressScore": round(score, 2),
            "confidence": round(min(0.95, 0.55 + (obs_count / 20.0)), 3),
            "crop": normalized_crop,
            "growthStage": growth_stage,
            "indicators": indicators,
            "stressMap": stress_map,
            "stressTimeSeries": stress_trends,
            "dataQuality": data_quality,
            "dataSources": {
                "gee": gee_status,
                "sentinel2_observations": len(s2_obs),
                "sentinel1_observations": len(s1_obs),
                "landsat_observations": len(lst_obs),
                "sensor_diagnostics": {
                    "sentinel2": s2_diag,
                    "sentinel1": s1_diag,
                    "landsat": lst_diag,
                }
            },
            "processing": {
                "status": "completed",
                "quality_checks": [
                    "AOI validated",
                    "GEE authentication verified",
                    "Sentinel-2 multi-spectral indices computed",
                    "Sentinel-1 SAR integrated" if s1_obs else "Sentinel-1 SAR unavailable",
                    "Landsat LST integrated" if has_lst else "Landsat LST unavailable",
                    "Pixel-level stress map generated",
                ],
                "requested_window": {
                    "start_date": start_date,
                    "end_date": end_date,
                },
                "breakdown": breakdown,
            },
        }

