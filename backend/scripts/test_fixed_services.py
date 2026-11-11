import json
import ee
from app.services.gee.gee_service import initialize_gee, gee_get_info

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

print("--- 1. FIXED S2 TEST ---")
from app.services.gee.sentinel2_service import mask_s2_clouds, calculate_indices
s2_col = (
    ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterBounds(geom)
    .filterDate(start_date, end_date)
    .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 80))
)
processed_s2 = s2_col.map(mask_s2_clouds).map(calculate_indices)

def reduce_s2(img):
    date = img.date().format('YYYY-MM-dd')
    stats = img.select([
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
    # Also get raw SCL to compute AOI valid pixel percentage and cloud percentage inside AOI
    scl_stats = img.select('SCL').reduceRegion(
        reducer=ee.Reducer.frequencyHistogram(),
        geometry=geom,
        scale=10,
        bestEffort=True
    )
    return ee.Feature(None, {
        'id': img.id(),
        'date': date,
        'scene_cloud_pct': img.get('CLOUDY_PIXEL_PERCENTAGE'),
        'stats': stats,
        'scl_hist': scl_stats.get('SCL')
    })

batch_s2 = ee.Dictionary({
    "scene_count": s2_col.size(),
    "features": processed_s2.map(reduce_s2).toList(1000)
})
res_s2 = gee_get_info(batch_s2)
print(f"S2 raw scenes: {res_s2['scene_count']}")
features_s2 = res_s2.get("features", [])
valid_s2 = [f for f in features_s2 if f.get('properties', {}).get('stats', {}).get('NDVI') is not None]
print(f"S2 valid scenes: {len(valid_s2)}")
if valid_s2:
    print("First valid S2 obs:", json.dumps(valid_s2[0], indent=2))

print("--- 2. FIXED S1 TEST ---")
from app.services.gee.sentinel1_service import calculate_s1_features
s1_col = (ee.ImageCollection("COPERNICUS/S1_GRD")
          .filterBounds(geom).filterDate(start_date, end_date)
          .filter(ee.Filter.eq('instrumentMode', 'IW'))
          .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
          .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH')))
processed_s1 = s1_col.map(calculate_s1_features)

def reduce_s1(img):
    date = img.date().format('YYYY-MM-dd')
    orbit = img.get('orbitProperties_pass')
    stats = img.select(['VV', 'VH', 'VV_VH_ratio', 'VV_VH_diff']).reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geom,
        scale=10,
        bestEffort=True,
        tileScale=2,
        maxPixels=1e9
    )
    return ee.Feature(None, {
        'id': img.id(),
        'date': date,
        'orbit': orbit,
        'stats': stats
    })

batch_s1 = ee.Dictionary({
    "scene_count": s1_col.size(),
    "features": processed_s1.map(reduce_s1).toList(1000)
})
res_s1 = gee_get_info(batch_s1)
print(f"S1 raw scenes: {res_s1['scene_count']}")
features_s1 = res_s1.get("features", [])
valid_s1 = [f for f in features_s1 if f.get('properties', {}).get('stats', {}).get('VV') is not None]
print(f"S1 valid scenes: {len(valid_s1)}")
if valid_s1:
    print("First valid S1 obs:", json.dumps(valid_s1[0], indent=2))

print("--- 3. FIXED LANDSAT TEST ---")
from app.services.gee.landsat_service import mask_landsat_sr, calculate_lst
l8_col = (
    ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
    .filterBounds(geom)
    .filterDate(start_date, end_date)
    .map(mask_landsat_sr)
    .map(calculate_lst)
)
l9_col = (
    ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")
    .filterBounds(geom)
    .filterDate(start_date, end_date)
    .map(mask_landsat_sr)
    .map(calculate_lst)
)
merged_col = l8_col.merge(l9_col)

def reduce_landsat(img):
    date = img.date().format('YYYY-MM-dd')
    means = img.select('LST').reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geom,
        scale=30,
        maxPixels=1e9
    )
    return ee.Feature(None, {
        'id': img.id(),
        'date': date,
        'LST': means.get('LST')
    })

batch_landsat = ee.Dictionary({
    "scene_count": merged_col.size(),
    "features": merged_col.map(reduce_landsat).toList(1000)
})
res_landsat = gee_get_info(batch_landsat)
print(f"Landsat raw scenes: {res_landsat['scene_count']}")
features_landsat = res_landsat.get("features", [])
valid_landsat = [f for f in features_landsat if f.get('properties', {}).get('LST') is not None]
print(f"Landsat valid scenes: {len(valid_landsat)}")
if valid_landsat:
    print("First valid Landsat obs:", json.dumps(valid_landsat[0], indent=2))
