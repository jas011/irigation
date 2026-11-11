import json
import ee
from app.services.gee.gee_service import initialize_gee, gee_get_info
from app.services.moisture.moisture_stress_service import get_pixel_level_stress
from app.services.gee.sentinel2_service import get_s2_time_series

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

s2_obs = get_s2_time_series(USER_FIELD, start_date, end_date)
print(f"S2 obs count: {len(s2_obs)}")

stress_map = get_pixel_level_stress(USER_FIELD, s2_obs, start_date, end_date)
print(f"Current Stress Map feature count: {len(stress_map.get('features', []))}")
