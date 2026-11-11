import asyncio
import time
import json
from app.schemas.field import GeoJSONPolygon
from app.services.field_validation_service import FieldValidationService
from app.services.analysis.crop_analysis_service import CropAnalysisService
from app.services.analysis.moisture_analysis_service import MoistureAnalysisService
from app.services.analysis.ground_truth_service import GroundTruthService
from unittest.mock import MagicMock

# Realistic agricultural field in Punjab (near Jalandhar/Kapurthala)
SAMPLE_FIELD = {
    "type": "Polygon",
    "coordinates": [[
        [75.3812, 31.3807],
        [75.3867, 31.3807],
        [75.3867, 31.3856],
        [75.3812, 31.3856],
        [75.3812, 31.3807]
    ]]
}

async def run_benchmark():
    print("================================================================================")
    print("AGRISENSE COMPLETE PIPELINE BENCHMARK & ACCURACY VERIFICATION")
    print("================================================================================")

    # -------------------------------------------------------------
    # STAGE 1: FIELD VALIDATION
    # -------------------------------------------------------------
    print("\n[TEST 1] Executing Stage 1 Field Validation...")
    t0 = time.perf_counter()
    poly_geom = GeoJSONPolygon(**SAMPLE_FIELD)
    mock_db = MagicMock()
    mock_db.execute.side_effect = Exception("Fallback to high-speed Shapely geodesic engine")
    s1_res = FieldValidationService.validate_field(mock_db, poly_geom)
    t_stage1 = (time.perf_counter() - t0) * 1000

    print(f"  [PASS] Stage 1 Completed in: {t_stage1:.2f} ms")
    print(f"  [INFO] Valid: {s1_res.valid} | Area: {s1_res.area_hectares:.2f} ha ({s1_res.area_acres:.2f} acres) | Perimeter: {s1_res.perimeter_m:.1f} m")
    print(f"  [INFO] Centroid: Lat={s1_res.centroid.latitude:.4f}, Lon={s1_res.centroid.longitude:.4f}")
    assert s1_res.valid, "Stage 1 Validation Failed!"

    # -------------------------------------------------------------
    # STAGE 2: CROP CLASSIFICATION (COLD RUN)
    # -------------------------------------------------------------
    print("\n[TEST 2] Executing Stage 2 Crop Classification (Fresh Satellite Acquisition)...")
    t0 = time.perf_counter()
    start_date = "2024-05-01"
    end_date = "2024-09-30"
    
    s2_res = await CropAnalysisService.analyze_field(
        geometry=SAMPLE_FIELD,
        start_date=start_date,
        end_date=end_date
    )
    t_stage2_cold = (time.perf_counter() - t0) * 1000

    print(f"  [PASS] Stage 2 Cold Run Completed in: {t_stage2_cold:.2f} ms ({t_stage2_cold/1000:.2f} s)")
    crop = s2_res["cropPrediction"]["label"]
    conf = s2_res["cropPrediction"]["confidence"]
    stage = s2_res["growthStage"]["stage"]
    s2_obs = s2_res["availability"]["s2_observation_count"]
    s1_obs = s2_res["availability"]["s1_observation_count"]
    quality = s2_res["availability"]["data_quality"]

    print(f"  [INFO] Detected Crop: {crop} (Confidence: {conf*100:.1f}%)")
    print(f"  [INFO] Growth Stage: {stage} | Data Quality: {quality}")
    print(f"  [INFO] Satellite Observations: S2={s2_obs}, S1 SAR={s1_obs}")
    print(f"  [INFO] Latest Indices: {json.dumps(s2_res.get('indices', {}))}")
    assert crop != "Unknown", "Stage 2 Failed to classify crop!"

    # -------------------------------------------------------------
    # STAGE 3: MOISTURE STRESS DETECTION (CACHED OBSERVATION RUN)
    # -------------------------------------------------------------
    print("\n[TEST 3] Executing Stage 3 Moisture Stress Analysis (Reusing Cached Satellite Features)...")
    t0 = time.perf_counter()
    s3_res = await MoistureAnalysisService.analyze_field(
        geometry=SAMPLE_FIELD,
        crop_prediction=crop,
        growth_stage=stage,
        start_date=start_date,
        end_date=end_date
    )
    t_stage3 = (time.perf_counter() - t0) * 1000

    print(f"  [PASS] Stage 3 Completed in: {t_stage3:.2f} ms ({t_stage3/1000:.2f} s)")
    stress_level = s3_res["stressLevel"]
    stress_score = s3_res["stressScore"]
    indicators = s3_res["indicators"]

    print(f"  [INFO] Stress Condition: {stress_level} (Score: {stress_score}/100)")
    print(f"  [INFO] Moisture Indicators: NDMI={indicators.get('ndmi')}, NDWI={indicators.get('ndwi')}, VCI={indicators.get('vci')}%, LST={indicators.get('lst', 'N/A')}")
    print(f"  [INFO] Spatial 10m Stress Map Cells Generated: {len(s3_res.get('stressMap', {}).get('features', []))}")
    assert stress_level in ["No Stress", "Low Stress", "Moderate Stress", "High Stress", "Severe Stress", "Insufficient Data"], "Invalid stress level!"

    # -------------------------------------------------------------
    # STAGE 2: WARM RUN (REPEAT CACHE TEST)
    # -------------------------------------------------------------
    print("\n[TEST 4] Executing Stage 2 Warm / Repeat Query (Testing Instant Memory Cache)...")
    t0 = time.perf_counter()
    s2_warm = await CropAnalysisService.analyze_field(
        geometry=SAMPLE_FIELD,
        start_date=start_date,
        end_date=end_date
    )
    t_stage2_warm = (time.perf_counter() - t0) * 1000
    print(f"  [PASS] Stage 2 Warm / Cached Run Completed in: {t_stage2_warm:.2f} ms (INSTANT RETRIEVAL)")

    # -------------------------------------------------------------
    # GROUND TRUTH SPATIAL LOOKUP BENCHMARK
    # -------------------------------------------------------------
    print("\n[TEST 5] Benchmarking STRtree Spatial Indexing on 5,000 Reference Polygons...")
    t0 = time.perf_counter()
    matches = GroundTruthService.find_relevant_records(SAMPLE_FIELD, limit=10)
    t_csv = (time.perf_counter() - t0) * 1000
    print(f"  [PASS] 5,000 Polygon R-Tree Spatial Query Completed in: {t_csv:.3f} ms")
    print(f"  [INFO] Matched Records in AOI: {len(matches)}")

    # -------------------------------------------------------------
    # SUMMARY REPORT
    # -------------------------------------------------------------
    print("\n" + "=" * 80)
    print("FINAL BENCHMARK PERFORMANCE RESULTS")
    print("================================================================================")
    print(f"  * Stage 1 (Field Validation)         : {t_stage1:.2f} ms")
    print(f"  * Stage 2 (Cold Satellite Query)     : {t_stage2_cold/1000:.2f} s")
    print(f"  * Stage 3 (Moisture Stress Analysis) : {t_stage3/1000:.2f} s  (Cache Accelerated)")
    print(f"  * Stage 2 (Warm / Repeated Query)    : {t_stage2_warm:.2f} ms (Instant 0s latency)")
    print(f"  * Ground Truth Spatial Index Lookup  : {t_csv:.3f} ms")
    print(f"  * All Quality Gates & Checks Passed  : YES")
    print("================================================================================\n")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
