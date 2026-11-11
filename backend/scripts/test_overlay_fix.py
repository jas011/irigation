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
s2_obs = get_s2_time_series(USER_FIELD, start_date, end_date)

s2_col = (
    ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterBounds(geom)
    .filterDate(start_date, end_date)
    .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 80))
    .map(mask_s2_clouds)
    .map(calculate_indices)
    .sort('system:time_start', False)
)

latest_img = s2_col.first()

grid_points = gee_get_info(latest_img.sample(
    region=geom,
    scale=10,
    numPixels=300,
    geometries=True,
    seed=42,
    tileScale=4
))

print("Raw sampled grid points count:", len(grid_points.get("features", [])))

features = []
ndvi_max = max(obs['NDVI'] for obs in s2_obs)
ndvi_min = min(obs['NDVI'] for obs in s2_obs)

for feat in grid_points.get('features', []):
    coords = feat.get('geometry', {}).get('coordinates')
    props = feat.get('properties', {})
    if not coords or props.get('NDVI') is None:
        continue
    p_ndvi = float(props.get('NDVI', 0.0))
    p_ndmi = float(props.get('NDMI', 0.0))
    p_ndwi = float(props.get('NDWI', 0.0))
    p_evi = float(props.get('EVI', 0.0))
    pixel_features = {
        "latest_ndvi": p_ndvi,
        "latest_ndmi": p_ndmi,
        "latest_ndwi": p_ndwi,
        "latest_evi": p_evi,
        "ndvi_max": ndvi_max,
        "ndvi_min": ndvi_min
    }
    score, stress_class, _ = calculate_stress_from_features(pixel_features, has_lst=False, has_s1=False)
    cell_geometry = clipped_sample_cell(coords, USER_FIELD)
    if not cell_geometry:
        continue
    features.append({
        "type": "Feature",
        "geometry": cell_geometry,
        "properties": {
            "stress_score": score,
            "stress_class": stress_class
        }
    })

print(f"Generated stress map cells count: {len(features)}")
if features:
    print("Sample feature properties:", features[0]["properties"])
