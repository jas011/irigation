import asyncio
import json
from app.services.gee.gee_service import initialize_gee
from app.services.analysis.crop_analysis_service import CropAnalysisService
from app.services.analysis.moisture_analysis_service import MoistureAnalysisService

initialize_gee()

# User's exact bounding box
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

async def test_user_field():
    print("Testing User's Exact Field with Date Window: 2026-04-22 to 2026-08-20\n")
    s2_res = await CropAnalysisService.analyze_field(
        geometry=USER_FIELD,
        start_date="2026-04-22",
        end_date="2026-08-20"
    )
    print("\n[Stage 2 Result]")
    print(f"Crop: {s2_res['cropPrediction']['label']} (Confidence: {s2_res['cropPrediction']['confidence']*100:.1f}%)")
    print(f"Growth Stage: {s2_res['growthStage']['stage']}")
    print(f"S2 Observations: {s2_res['availability']['s2_observation_count']}")
    print(f"S1 SAR Observations: {s2_res['availability']['s1_observation_count']}")
    print(f"Data Quality: {s2_res['availability']['data_quality']}")
    print("Latest Indices:", json.dumps(s2_res.get('indices', {}), indent=2))

    s3_res = await MoistureAnalysisService.analyze_field(
        geometry=USER_FIELD,
        crop_prediction=s2_res['cropPrediction']['label'],
        growth_stage=s2_res['growthStage']['stage'],
        start_date="2026-04-22",
        end_date="2026-08-20"
    )
    print("\n[Stage 3 Result]")
    print(f"Stress Condition: {s3_res['stressLevel']} (Score: {s3_res['stressScore']}/100)")
    print("Indicators:", json.dumps(s3_res.get('indicators', {}), indent=2))

if __name__ == "__main__":
    asyncio.run(test_user_field())
