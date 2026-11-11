import json
from app.services.moisture.moisture_stress_service import calculate_stress_from_features

p_feat = {
    "latest_ndvi": 0.746,
    "latest_ndmi": 0.431,
    "latest_ndwi": -0.607,
    "latest_evi": 0.712,
    "ndvi_max": 0.746,
    "ndvi_min": 0.100,
    "latest_lst": 35.64,
    "latest_vv_vh_ratio": 8.90
}

score, stress_class, breakdown = calculate_stress_from_features(p_feat, has_lst=True, has_s1=True)
print("Pixel score with full fusion:", score, "Class:", stress_class)
print("Breakdown:", breakdown)
