import json
import ee
from app.services.gee.gee_service import initialize_gee, gee_get_info
from app.services.gee.sentinel2_service import calculate_indices, mask_s2_clouds

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
geom = ee.Geometry(USER_FIELD)
start_date = "2026-04-22"
end_date = "2026-08-20"

s2_col = (
    ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterBounds(geom)
    .filterDate(start_date, end_date)
    .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 50))
    .map(mask_s2_clouds)
    .map(calculate_indices)
)

# Test 1: sample on latest image with select
latest = s2_col.sort('system:time_start', False).first().select(['NDVI', 'NDMI', 'NDWI', 'EVI'])
pts1 = latest.sample(region=geom, scale=10, numPixels=100, geometries=True, dropNulls=False)
res1 = gee_get_info(pts1)
print("Test 1 (latest select dropNulls=False):", len(res1.get("features", [])))
if res1.get("features"):
    print("Test 1 sample props:", res1["features"][0])

# Test 2: sample on median composite
median_img = s2_col.select(['NDVI', 'NDMI', 'NDWI', 'EVI']).median()
pts2 = median_img.sample(region=geom, scale=10, numPixels=100, geometries=True, dropNulls=False)
res2 = gee_get_info(pts2)
print("Test 2 (median select dropNulls=False):", len(res2.get("features", [])))
if res2.get("features"):
    print("Test 2 sample props:", res2["features"][0])
