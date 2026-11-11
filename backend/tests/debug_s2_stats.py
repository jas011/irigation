import ee
import json
from app.services.gee.gee_service import initialize_gee, gee_get_info
from app.services.gee.sentinel2_service import mask_s2_clouds, calculate_indices

initialize_gee()

geom = ee.Geometry.Polygon([[
    [75.7948, 30.9086],
    [75.799, 30.9086],
    [75.799, 30.9095],
    [75.7948, 30.9095],
    [75.7948, 30.9086]
]])

s2_col = (
    ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterBounds(geom)
    .filterDate("2026-04-22", "2026-08-20")
    .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 80))
)

processed_col = s2_col.map(mask_s2_clouds).map(calculate_indices)

def inspect_img(img):
    date = img.date().format('YYYY-MM-dd')
    stats = img.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geom,
        scale=10,
        maxPixels=1e9
    )
    return ee.Feature(None, {'date': date, 'stats': stats})

results = gee_get_info(processed_col.limit(5).map(inspect_img))
print("SAMPLE SENTINEL-2 STATS:")
print(json.dumps(results, indent=2))
