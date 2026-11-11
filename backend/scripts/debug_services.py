import json
import ee
from app.services.gee.gee_service import initialize_gee, gee_get_info
from app.services.gee.sentinel2_service import mask_s2_clouds, calculate_indices
from app.services.gee.sentinel1_service import calculate_s1_features
from app.services.gee.landsat_service import mask_landsat_sr, calculate_lst

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

print("--- DEBUG S2 REDUCE ---")
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
    return ee.Feature(None, {'date': date, 'stats': stats})

s2_sample = processed_s2.limit(5).map(reduce_s2)
print("S2 processed sample:", json.dumps(gee_get_info(s2_sample), indent=2))

print("--- DEBUG S1 REDUCE ---")
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
    return ee.Feature(None, {'date': date, 'orbit': orbit, 'stats': stats})

s1_sample = processed_s1.limit(5).map(reduce_s1)
print("S1 processed sample:", json.dumps(gee_get_info(s1_sample), indent=2))

print("--- DEBUG LANDSAT REDUCE ---")
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
    return ee.Feature(None, {'date': date, 'LST': means.get('LST')})

landsat_sample = merged_col.limit(5).map(reduce_landsat)
print("Landsat processed sample:", json.dumps(gee_get_info(landsat_sample), indent=2))
