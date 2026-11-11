import json
import ee
from app.services.gee.gee_service import initialize_gee, gee_get_info
from app.services.crop.crop_classification_service import _training_asset, _s2_collection, calculate_indices, mask_s2_clouds

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
start_date = "2026-04-22"
end_date = "2026-08-20"

training, labels, training_diagnostic, train_counts, validation_counts = _training_asset()
geom = ee.Geometry(USER_FIELD)

# Check how many training features intersect geom
intersecting = training.filterBounds(geom).size().getInfo()
print("Training features intersecting user field:", intersecting)

# Check training features in 10km buffer
buffer_geom = geom.buffer(10000)
intersecting_10k = training.filterBounds(buffer_geom).size().getInfo()
print("Training features within 10km:", intersecting_10k)
