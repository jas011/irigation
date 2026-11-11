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

fc = processed_col.map(reduce_image)

print("--- Calling getInfo directly on FeatureCollection ---")
fc_direct = gee_get_info(fc)
print("Direct FC type:", type(fc_direct))
print("Direct FC features count:", len(fc_direct.get("features", [])))
valid = 0
for f in fc_direct.get("features", []):
    st = f.get("properties", {}).get("stats", {})
    if st and st.get("NDVI") is not None:
        valid += 1
print(f"Direct FC Valid stats count: {valid}")

print("--- Calling getInfo on ee.Dictionary with toList or list ---")
dict_with_list = ee.Dictionary({
    "scene_count": s2_col.size(),
    "features": fc.toList(1000)
})
dict_res = gee_get_info(dict_with_list)
print("Dict res scene_count:", dict_res.get("scene_count"))
print("Dict res features type:", type(dict_res.get("features")))
print("Dict res features count:", len(dict_res.get("features", [])))
valid_dict = 0
for f in dict_res.get("features", []):
    st = f.get("properties", {}).get("stats", {})
    if st and st.get("NDVI") is not None:
        valid_dict += 1
print(f"Dict res Valid stats count: {valid_dict}")
