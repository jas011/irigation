import json
import ee
from app.services.gee.gee_service import initialize_gee, gee_get_info
from app.services.crop.crop_classification_service import _training_asset, build_fused_feature_image, _balanced_samples, _validation_metrics, _field_entropy, _as_integer_id, MAX_SAMPLES_PER_CLASS, MIN_TRAINING_FEATURES_PER_CLASS, MIN_DOMINANT_CLASS_PCT, MIN_FIELD_PROBABILITY
from app.utils.geometry import clipped_sample_cell

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

print("Building fused features...")
training, labels, training_diagnostic, train_counts, validation_counts = _training_asset()
fused = build_fused_feature_image(USER_FIELD, start_date, end_date)
class_ids = sorted(labels)
train_features = training.filter(ee.Filter.neq("_spatial_fold", 0))
validation_features = training.filter(ee.Filter.eq("_spatial_fold", 0))

model_image = fused["image"].updateMask(fused["required_mask"])
train_samples = _balanced_samples(model_image, train_features, class_ids, fused["feature_bands"], 42)
validation_samples = _balanced_samples(model_image, validation_features, class_ids, fused["feature_bands"], 84)

classifier = ee.Classifier.smileRandomForest(numberOfTrees=100, seed=42, minLeafPopulation=2).train(
    features=train_samples, classProperty="crop_id", inputProperties=fused["feature_bands"]
)
validated = validation_samples.classify(classifier)
prediction = model_image.classify(classifier).rename("crop_id").clip(fused["geometry"])
probability = model_image.classify(classifier.setOutputMode("PROBABILITY")).rename("prediction_probability").clip(fused["geometry"])

print("Running matrix & histogram...")
eval_query = ee.Dictionary({
    "matrix": validated.errorMatrix("crop_id", "classification", class_ids).array(),
    "histogram": prediction.reduceRegion(
        reducer=ee.Reducer.frequencyHistogram(), geometry=fused["geometry"], scale=10,
        maxPixels=100_000_000, bestEffort=True, tileScale=4,
    ).get("crop_id")
})
res = gee_get_info(eval_query)
print("Matrix & Histogram Result:", res)

print("Running sampled points...")
sampled = prediction.addBands(probability).sample(
    region=fused["geometry"], scale=10, numPixels=200, geometries=True, tileScale=4
)
sampled_res = gee_get_info(sampled)
print("Sampled count:", len(sampled_res.get("features", [])))
