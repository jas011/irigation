import ee
from app.services.gee.gee_service import initialize_gee, gee_get_info

initialize_gee()

geom = ee.Geometry.Point([75.8, 30.9])
latest_s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(geom).sort("system:time_start", False).first()
latest_date = latest_s2.date().format("YYYY-MM-dd").getInfo()

print(f"LATEST AVAILABLE SENTINEL-2 IMAGE IN GEE: {latest_date}")

latest_s1 = ee.ImageCollection("COPERNICUS/S1_GRD").filterBounds(geom).sort("system:time_start", False).first()
latest_s1_date = latest_s1.date().format("YYYY-MM-dd").getInfo()
print(f"LATEST AVAILABLE SENTINEL-1 IMAGE IN GEE: {latest_s1_date}")
