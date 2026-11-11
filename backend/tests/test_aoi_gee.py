import ee
import json
from app.services.gee.gee_service import initialize_gee, gee_get_info
from app.services.gee.sentinel2_service import mask_s2_clouds, calculate_indices
from app.services.gee.sentinel1_service import calculate_s1_features

initialize_gee()

geom = ee.Geometry.Polygon([[
    [76.1933, 30.7041],
    [76.1949, 30.7041],
    [76.1949, 30.7058],
    [76.1933, 30.7058],
    [76.1933, 30.7041]
]])

s2_col = (
    ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterBounds(geom)
    .filterDate("2024-05-01", "2024-09-30")
    .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 80))
)

print("S2 Scene Count in 2024:", s2_col.size().getInfo())

# Also check 2026 dates (future/current year check)
s2_col_2026 = (
    ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterBounds(geom)
    .filterDate("2026-04-22", "2026-08-20")
)
print("S2 Scene Count in 2026:", s2_col_2026.size().getInfo())

# Let's inspect raw image properties for first 3 scenes in 2026
first_scenes = s2_col_2026.limit(3)
def get_props(img):
    return ee.Feature(None, {
        'id': img.id(),
        'date': img.date().format('YYYY-MM-dd'),
        'cloudy_pixel_pct': img.get('CLOUDY_PIXEL_PERCENTAGE')
    })
print("2026 Scenes:", gee_get_info(first_scenes.map(get_props)))
