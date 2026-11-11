import json
import ee
from app.services.gee.gee_service import initialize_gee
from app.services.moisture.moisture_stress_service import calculate_stress_from_features, determine_stress_class
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

async def check():
    res = await MoistureAnalysisService.analyze_field(
        geometry=USER_FIELD,
        crop_prediction="Paddy",
        growth_stage="Flowering",
        start_date="2026-04-22",
        end_date="2026-08-20"
    )
    print("Field Stress Level:", res["stressLevel"], "Score:", res["stressScore"])
    features = res.get("stressMap", {}).get("features", [])
    if features:
        sample_scores = [f["properties"]["stress_score"] for f in features[:10]]
        sample_classes = [f["properties"]["stress_class"] for f in features[:10]]
        print("Sample pixel stress scores:", sample_scores)
        print("Sample pixel stress classes:", sample_classes)

import asyncio
asyncio.run(check())
