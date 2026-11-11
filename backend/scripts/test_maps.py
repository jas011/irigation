import json
import ee
from app.services.gee.gee_service import initialize_gee, gee_get_info
from app.services.gee.sentinel2_service import calculate_indices, mask_s2_clouds, get_s2_time_series
from app.services.moisture.moisture_stress_service import calculate_stress_from_features
from app.utils.geometry import clipped_sample_cell

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
geom = ee.Geometry(USER_FIELD)

s2_col = (
    ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterBounds(geom)
    .filterDate(start_date, end_date)
    .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 80))
    .map(mask_s2_clouds)
    .map(calculate_indices)
    .sort('system:time_start', False)
)
latest_img = s2_col.first().select(['NDVI', 'NDMI', 'NDWI', 'EVI'])
grid_points = gee_get_info(latest_img.sample(
    region=geom,
    scale=10,
    numPixels=250,
    geometries=True,
    dropNulls=False,
    seed=42,
    tileScale=4
))

pts = grid_points.get("features", [])
print(f"Sampled points count: {len(pts)}")

# 1. Stress map
stress_features = []
for pt in pts:
    coords = pt.get("geometry", {}).get("coordinates")
    props = pt.get("properties", {})
    if not coords or props.get("NDVI") is None:
        continue
    p_feat = {
        "latest_ndvi": float(props.get("NDVI", 0.0)),
        "latest_ndmi": float(props.get("NDMI", 0.0)),
        "latest_ndwi": float(props.get("NDWI", 0.0)),
        "latest_evi": float(props.get("EVI", 0.0)),
        "ndvi_max": 0.8,
        "ndvi_min": 0.1
    }
    score, stress_class, _ = calculate_stress_from_features(p_feat, has_lst=False, has_s1=False)
    cell = clipped_sample_cell(coords, USER_FIELD)
    if cell:
        stress_features.append({
            "type": "Feature",
            "geometry": cell,
            "properties": {"stress_score": score, "stress_class": stress_class}
        })
print(f"Generated stress features: {len(stress_features)}")

# 2. Crop map
crop_features = []
predicted_crop = "Paddy"
for pt in pts:
    coords = pt.get("geometry", {}).get("coordinates")
    props = pt.get("properties", {})
    if not coords:
        continue
    ndvi_val = props.get("NDVI")
    ndwi_val = props.get("NDWI")
    if ndwi_val is not None and float(ndwi_val) > 0.1 and (ndvi_val is None or float(ndvi_val) < 0.2):
        pixel_crop = "Water"
    elif ndvi_val is not None and float(ndvi_val) < 0.22:
        pixel_crop = "Bare Soil"
    else:
        pixel_crop = predicted_crop
    cell = clipped_sample_cell(coords, USER_FIELD)
    if cell:
        crop_features.append({
            "type": "Feature",
            "geometry": cell,
            "properties": {"crop": pixel_crop}
        })
print(f"Generated crop features: {len(crop_features)}")
