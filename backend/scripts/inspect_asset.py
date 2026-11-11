import json
import ee
from app.services.gee.gee_service import initialize_gee, gee_get_info

initialize_gee()
asset_id = "projects/agrisense-satellite/assets/crop_training"
fc = ee.FeatureCollection(asset_id)
size = fc.size().getInfo()
print("Asset size:", size)
first = fc.first().getInfo()
print("First feature:", json.dumps(first, indent=2))
hist = fc.aggregate_histogram("crop_name").getInfo()
print("Crop histogram:", json.dumps(hist, indent=2))
bounds = fc.geometry().bounds().getInfo()
print("Bounds:", bounds)
