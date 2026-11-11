import ee
import json
from app.services.gee.gee_service import initialize_gee, gee_get_info
from app.services.gee.sentinel2_service import mask_s2_clouds, calculate_indices

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

s2_col = (
    ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterBounds(geom)
    .filterDate("2026-04-22", "2026-08-20")
    .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 80))
)

processed_col = s2_col.map(mask_s2_clouds).map(calculate_indices)

def reduce_test(img):
    date = img.date().format('YYYY-MM-dd')
    stats = img.select(['NDVI', 'EVI', 'NDMI', 'NDWI', 'SAVI', 'B8', 'B4']).reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geom,
        scale=10,
        bestEffort=True,
        tileScale=2
    )
    return ee.Feature(None, {'date': date, 'stats': stats})

query = ee.Dictionary({
    "count": s2_col.size(),
    "items": processed_col.map(reduce_test)
})

res = gee_get_info(query)
print("Count:", res.get("count"))
features = res.get("items", {}).get("features", [])
valid = [f for f in features if f.get("properties", {}).get("stats", {}).get("NDVI") is not None]
print(f"Total features: {len(features)}, Valid with NDVI: {len(valid)}")
if valid:
    print("Sample valid observation:", valid[0]["properties"])
