import json
import ee
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
start_date = "2026-04-22"
end_date = "2026-08-20"

s2_col = (
    ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterBounds(geom)
    .filterDate(start_date, end_date)
    .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 80))
)
processed_col = s2_col.map(mask_s2_clouds).map(calculate_indices)

def reduce_image(image: ee.Image) -> ee.Feature:
    date = image.date().format('YYYY-MM-dd')
    stats = image.select([
        'NDVI', 'EVI', 'NDMI', 'NDWI', 'NDRE', 'GNDVI', 'SAVI',
        'B2', 'B3', 'B4', 'B8', 'B11'
    ]).reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geom,
        scale=10,
        bestEffort=True,
        tileScale=2,
        maxPixels=1e9
    )
    return ee.Feature(None, {
        'date': date,
        'stats': stats
    })

batch_query = ee.Dictionary({
    "scene_count": s2_col.size(),
    "features": processed_col.map(reduce_image)
})
batch_res = gee_get_info(batch_query)
print("Keys in batch_res:", batch_res.keys())
print("Type of features:", type(batch_res.get("features")))
feats = batch_res.get("features")
if isinstance(feats, dict):
    print("Features dict keys:", feats.keys())
    print("Features count:", len(feats.get("features", [])))
    print("First 3 features:", feats.get("features", [])[:3])
    # Let's count how many have non-empty stats
    valid = 0
    empty = 0
    for f in feats.get("features", []):
        st = f.get("properties", {}).get("stats", {})
        if st and st.get("NDVI") is not None:
            valid += 1
        else:
            empty += 1
    print(f"Valid stats count: {valid}, empty stats count: {empty}")
