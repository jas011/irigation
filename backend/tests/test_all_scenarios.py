import asyncio
import json
from app.services.gee.gee_service import initialize_gee
from app.services.analysis.crop_analysis_service import CropAnalysisService
from app.services.analysis.moisture_analysis_service import MoistureAnalysisService

initialize_gee()

# 1. User Field in Punjab
USER_FIELD = {
    "type": "Polygon",
    "coordinates": [[
        [76.1933, 30.7041],
        [76.1949, 30.7041],
        [76.1949, 30.7058],
        [76.1933, 30.7058],
        [76.1933, 30.7041]
    ]]
}

# 2. Large Field in Ludhiana, Punjab
LUDHIANA_LARGE_FIELD = {
    "type": "Polygon",
    "coordinates": [[
        [75.8200, 30.8800],
        [75.8300, 30.8800],
        [75.8300, 30.8900],
        [75.8200, 30.8900],
        [75.8200, 30.8800]
    ]]
}

# 3. Small Field in Bathinda, Punjab
BATHINDA_SMALL_FIELD = {
    "type": "Polygon",
    "coordinates": [[
        [74.9400, 30.2100],
        [74.9420, 30.2100],
        [74.9420, 30.2120],
        [74.9400, 30.2120],
        [74.9400, 30.2100]
    ]]
}

async def run_scenario(name: str, geometry: dict, start_date: str, end_date: str):
    print(f"\n{'='*70}\nSCENARIO: {name} (Window: {start_date} to {end_date})\n{'='*70}")
    crop_res = await CropAnalysisService.analyze_field(
        geometry=geometry,
        start_date=start_date,
        end_date=end_date
    )
    label = crop_res['cropPrediction']['label']
    conf = crop_res['cropPrediction']['confidence']
    s2_count = crop_res['availability']['s2_observation_count']
    s1_count = crop_res['availability']['s1_observation_count']
    quality = crop_res['availability']['data_quality']
    stage = crop_res['growthStage']['stage']
    print(f"-> Crop Prediction: {label} ({conf*100:.1f}%) | Stage: {stage} | S2: {s2_count} | S1: {s1_count} | Quality: {quality}")

    moisture_res = await MoistureAnalysisService.analyze_field(
        geometry=geometry,
        crop_prediction=label,
        growth_stage=stage,
        start_date=start_date,
        end_date=end_date
    )
    stress = moisture_res['stressLevel']
    score = moisture_res['stressScore']
    inds = moisture_res.get('indicators', {})
    print(f"-> Moisture Stress: {stress} (Score: {score}/100) | NDMI: {inds.get('ndmi')} | NDWI: {inds.get('ndwi')} | LST: {inds.get('lst')}")

async def main():
    # Scenario 1: User field in Punjab (2026 Kharif)
    await run_scenario("User Field (Punjab)", USER_FIELD, "2026-04-22", "2026-08-20")

    # Scenario 2: Ludhiana Large Field
    await run_scenario("Ludhiana Large Field", LUDHIANA_LARGE_FIELD, "2026-04-22", "2026-08-20")

    # Scenario 3: Bathinda Small Field
    await run_scenario("Bathinda Small Field", BATHINDA_SMALL_FIELD, "2026-04-22", "2026-08-20")

    # Scenario 4: Ultra-short / Non-existent 1-day window (Testing "Insufficient Data" protection)
    await run_scenario("Insufficient Data Gate (1-day window)", USER_FIELD, "2026-04-22", "2026-04-23")

if __name__ == "__main__":
    asyncio.run(main())
