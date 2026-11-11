import os
import json
import ee
from app.services.gee.gee_service import initialize_gee, gee_get_info

initialize_gee()

# User's exact polygon
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

print("="*60)
print("DIAGNOSING SENTINEL-2...")
print("="*60)

s2_col = (
    ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterBounds(geom)
    .filterDate(start_date, end_date)
)
s2_size = s2_col.size().getInfo()
print(f"Total Sentinel-2 scenes in bounds & date range: {s2_size}")

if s2_size > 0:
    first_few = s2_col.limit(5)
    def inspect_s2(img):
        date = img.date().format('YYYY-MM-dd')
        cloud_pct = img.get('CLOUDY_PIXEL_PERCENTAGE')
        cloud_score = img.get('CLOUD_COVERAGE_ASSESSMENT')
        img_id = img.id()
        # Check raw bands stats
        raw_stats = img.select(['B2', 'B4', 'B8', 'B11', 'SCL']).reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geom,
            scale=10,
            bestEffort=True
        )
        # Check SCL frequency
        scl_hist = img.select('SCL').reduceRegion(
            reducer=ee.Reducer.frequencyHistogram(),
            geometry=geom,
            scale=10,
            bestEffort=True
        )
        return ee.Feature(None, {
            'id': img_id,
            'date': date,
            'CLOUDY_PIXEL_PERCENTAGE': cloud_pct,
            'raw_stats': raw_stats,
            'scl_hist': scl_hist
        })
    info = gee_get_info(first_few.map(inspect_s2))
    print(json.dumps(info, indent=2))

print("="*60)
print("DIAGNOSING SENTINEL-1...")
print("="*60)

s1_col = (
    ee.ImageCollection("COPERNICUS/S1_GRD")
    .filterBounds(geom)
    .filterDate(start_date, end_date)
    .filter(ee.Filter.eq('instrumentMode', 'IW'))
    .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
    .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
)
s1_size = s1_col.size().getInfo()
print(f"Total Sentinel-1 scenes: {s1_size}")

if s1_size > 0:
    first_s1 = s1_col.limit(5)
    def inspect_s1(img):
        date = img.date().format('YYYY-MM-dd')
        img_id = img.id()
        orbit = img.get('orbitProperties_pass')
        stats = img.select(['VV', 'VH']).reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geom,
            scale=10,
            bestEffort=True
        )
        # Check footprint intersection
        footprint = img.geometry()
        intersection = footprint.intersection(geom, 1)
        aoi_area = geom.area(1)
        inter_area = intersection.area(1)
        return ee.Feature(None, {
            'id': img_id,
            'date': date,
            'orbit': orbit,
            'stats': stats,
            'aoi_area': aoi_area,
            'inter_area': inter_area
        })
    s1_info = gee_get_info(first_s1.map(inspect_s1))
    print(json.dumps(s1_info, indent=2))

print("="*60)
print("DIAGNOSING LANDSAT...")
print("="*60)

l8_col = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").filterBounds(geom).filterDate(start_date, end_date)
l9_col = ee.ImageCollection("LANDSAT/LC09/C02/T1_L2").filterBounds(geom).filterDate(start_date, end_date)
merged_landsat = l8_col.merge(l9_col)
landsat_size = merged_landsat.size().getInfo()
print(f"Total Landsat scenes: {landsat_size}")

if landsat_size > 0:
    first_landsat = merged_landsat.limit(5)
    def inspect_landsat(img):
        date = img.date().format('YYYY-MM-dd')
        img_id = img.id()
        bands = img.bandNames()
        st_stats = img.select('ST_B10').reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geom,
            scale=30,
            bestEffort=True
        )
        qa_stats = img.select('QA_PIXEL').reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geom,
            scale=30,
            bestEffort=True
        )
        return ee.Feature(None, {
            'id': img_id,
            'date': date,
            'st_stats': st_stats,
            'qa_stats': qa_stats
        })
    landsat_info = gee_get_info(first_landsat.map(inspect_landsat))
    print(json.dumps(landsat_info, indent=2))
