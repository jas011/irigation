import asyncio
import json
from app.services.gee.gee_service import initialize_gee
from app.services.analysis.crop_analysis_service import CropAnalysisService
from app.services.analysis.moisture_analysis_service import MoistureAnalysisService

initialize_gee()

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
start_date = "2026-04-22"
end_date = "2026-08-20"

async def test():
    print("Testing Crop Analysis Service...")
    crop_res = await CropAnalysisService.analyze_field(
        geometry=USER_FIELD,
        start_date=start_date,
        end_date=end_date
    )
    c_map = crop_res.get("classificationMap", {})
    c_features = c_map.get("features", [])
    print(f"Crop Classification Map: type={c_map.get('type')}, features_count={len(c_features)}")
    if c_features:
        print(f"Sample crop feature: {json.dumps(c_features[0])}")

    print("\nTesting Moisture Analysis Service...")
    moisture_res = await MoistureAnalysisService.analyze_field(
        geometry=USER_FIELD,
        crop_prediction=crop_res["cropPrediction"]["label"],
        growth_stage=crop_res["growthStage"]["stage"],
        start_date=start_date,
        end_date=end_date
    )
    m_map = moisture_res.get("stressMap", {})
    m_features = m_map.get("features", [])
    print(f"Moisture Stress Map: type={m_map.get('type')}, features_count={len(m_features)}")
    if m_features:
        print(f"Sample stress feature: {json.dumps(m_features[0])}")

if __name__ == "__main__":
    asyncio.run(test())
