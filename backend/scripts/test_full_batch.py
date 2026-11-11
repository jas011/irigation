import json
import ee
from app.services.gee.gee_service import initialize_gee, gee_get_info
from app.services.gee.sentinel2_service import get_s2_time_series_with_metadata
from app.services.gee.sentinel1_service import get_s1_time_series_with_metadata
from app.services.gee.landsat_service import get_landsat_lst_time_series
from app.services.crop.crop_classification_service import run_spatial_classification

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

print("--- TESTING SENTINEL-2 SERVICE DIRECTLY ---")
s2_res = get_s2_time_series_with_metadata(USER_FIELD, start_date, end_date)
print(f"S2 Result: count={s2_res.get('scene_count')}, valid={s2_res.get('valid_scene_count')}, obs_len={len(s2_res.get('observations', []))}")

print("--- TESTING SENTINEL-1 SERVICE DIRECTLY ---")
s1_res = get_s1_time_series_with_metadata(USER_FIELD, start_date, end_date)
print(f"S1 Result: count={s1_res.get('scene_count')}, valid={s1_res.get('valid_scene_count')}, obs_len={len(s1_res.get('observations', []))}")

print("--- TESTING LANDSAT SERVICE DIRECTLY ---")
lst_res = get_landsat_lst_time_series(USER_FIELD, start_date, end_date)
print(f"Landsat Result: obs_len={len(lst_res)}")

print("--- TESTING GEE RANDOM FOREST DIRECTLY ---")
try:
    rf_res = run_spatial_classification(USER_FIELD, start_date, end_date)
    print(f"RF Result: crop={rf_res.get('crop')}, conf={rf_res.get('confidence')}")
except Exception as e:
    import traceback
    print("RF Exception:", e)
    traceback.print_exc()
