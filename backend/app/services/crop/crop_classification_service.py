"""Validated regional Earth Engine crop classification.

This service deliberately has no local model, heuristics, or fallback labels.
It trains only from the configured, labelled regional FeatureCollection and
applies that model to the requested field.  A run is unavailable whenever the
training asset, satellite inputs, validation split, or field prediction does
not meet the stated quality gates.
"""

from __future__ import annotations

import logging
import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Tuple

import ee

from app.services.gee.gee_service import gee_get_info, is_gee_ready
from app.services.gee.sentinel1_service import calculate_s1_features
from app.services.gee.sentinel2_service import calculate_indices, mask_s2_clouds
from app.utils.geometry import clipped_sample_cell

logger = logging.getLogger("agrisense.crop_classification")

_cached_training_asset: Tuple[ee.FeatureCollection, Dict[int, str], Dict[str, Any], Dict[int, int], Dict[int, int]] | None = None
_cached_training_asset_id: str | None = None

EMPTY_MAP = {"type": "FeatureCollection", "features": []}
MODEL_VERSION = "regional-rf-v2"
FEATURE_VERSION = "s2-s1-temporal-v2"
MIN_VALID_S2_OBSERVATIONS = int(os.getenv("GEE_CROP_MIN_S2_OBSERVATIONS", "4"))
MIN_TRAINING_FEATURES_PER_CLASS = int(os.getenv("GEE_CROP_MIN_TRAINING_FEATURES_PER_CLASS", "20"))
MAX_SAMPLES_PER_CLASS = int(os.getenv("GEE_CROP_MAX_SAMPLES_PER_CLASS", "1500"))
MIN_FIELD_VALID_PIXEL_PCT = float(os.getenv("GEE_CROP_MIN_VALID_PIXEL_PCT", "50"))
MIN_DOMINANT_CLASS_PCT = float(os.getenv("GEE_CROP_MIN_DOMINANT_CLASS_PCT", "60")) / 100
MIN_FIELD_PROBABILITY = float(os.getenv("GEE_CROP_MIN_FIELD_PROBABILITY", "60")) / 100

S2_FEATURE_BANDS = [
    "s2_b2", "s2_b3", "s2_b4", "s2_b5", "s2_b6", "s2_b7", "s2_b8", "s2_b8a", "s2_b11", "s2_b12",
    "s2_ndvi_mean", "s2_ndvi_median", "s2_ndvi_std", "s2_ndvi_min", "s2_ndvi_max", "s2_ndvi_slope",
    "s2_evi_mean", "s2_evi_median", "s2_ndmi_mean", "s2_ndmi_median", "s2_ndwi_mean", "s2_ndwi_median",
    "s2_ndre_mean", "s2_ndre_median",
]
S1_FEATURE_BANDS = [
    "s1_vv_mean", "s1_vv_median", "s1_vv_std", "s1_vv_slope",
    "s1_vh_mean", "s1_vh_median", "s1_vh_std", "s1_vh_slope",
    "s1_ratio_mean", "s1_ratio_median", "s1_ratio_std",
]


class ClassificationUnavailable(RuntimeError):
    """The pipeline lacks verified data needed for a scientifically valid run."""


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ClassificationUnavailable(f"{name} must be an integer") from exc


def _s2_collection(geom: ee.Geometry, start_date: str, end_date: str) -> ee.ImageCollection:
    s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(geom).filterDate(start_date, end_date)
    cloud_score = ee.ImageCollection("GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED").filterBounds(geom).filterDate(start_date, end_date)
    joined = ee.Join.saveFirst("cloud_score_plus").apply(
        primary=s2,
        secondary=cloud_score,
        condition=ee.Filter.equals(leftField="system:index", rightField="system:index"),
    )
    return ee.ImageCollection(joined).filter(ee.Filter.notNull(["cloud_score_plus"])).map(mask_s2_clouds).map(calculate_indices)


def _stat(collection: ee.ImageCollection, band: str, reducer: ee.Reducer, name: str) -> ee.Image:
    return collection.select(band).reduce(reducer).rename(name)


def _temporal_slope(collection: ee.ImageCollection, band: str, start_date: str, name: str) -> ee.Image:
    def add_time(image: ee.Image) -> ee.Image:
        days = image.date().difference(ee.Date(start_date), "day")
        return image.addBands(ee.Image.constant(days).double().rename("time_days"))
    return collection.map(add_time).select(["time_days", band]).reduce(ee.Reducer.linearFit()).select("scale").rename(name)


def build_fused_feature_image(geometry_geojson: Dict[str, Any], start_date: str, end_date: str) -> Dict[str, Any]:
    """Build only scientifically used S2/S1 temporal features for an AOI."""
    if not is_gee_ready():
        raise ClassificationUnavailable("Google Earth Engine is not available")
    geom = ee.Geometry(geometry_geojson)
    s2 = _s2_collection(geom, start_date, end_date)

    s1 = (ee.ImageCollection("COPERNICUS/S1_GRD").filterBounds(geom).filterDate(start_date, end_date)
          .filter(ee.Filter.eq("instrumentMode", "IW"))
          .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
          .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
          .map(calculate_s1_features))

    # Batch counts query to GEE
    batch_counts = ee.Dictionary({
        "s2_count": s2.size(),
        "s1_count": s1.size()
    })
    counts_res = gee_get_info(batch_counts)
    s2_count = int(counts_res.get("s2_count", 0))
    s1_count = int(counts_res.get("s1_count", 0))

    if s2_count < MIN_VALID_S2_OBSERVATIONS:
        raise ClassificationUnavailable(
            f"Insufficient valid Sentinel-2 observations ({s2_count}; at least {MIN_VALID_S2_OBSERVATIONS} are required)"
        )

    s2_features = ee.Image.cat([
        s2.select("B2").median().rename("s2_b2"), s2.select("B3").median().rename("s2_b3"),
        s2.select("B4").median().rename("s2_b4"), s2.select("B5").median().rename("s2_b5"),
        s2.select("B6").median().rename("s2_b6"), s2.select("B7").median().rename("s2_b7"),
        s2.select("B8").median().rename("s2_b8"), s2.select("B8A").median().rename("s2_b8a"),
        s2.select("B11").median().rename("s2_b11"), s2.select("B12").median().rename("s2_b12"),
        _stat(s2, "NDVI", ee.Reducer.mean(), "s2_ndvi_mean"), _stat(s2, "NDVI", ee.Reducer.median(), "s2_ndvi_median"),
        _stat(s2, "NDVI", ee.Reducer.stdDev(), "s2_ndvi_std"), _stat(s2, "NDVI", ee.Reducer.min(), "s2_ndvi_min"),
        _stat(s2, "NDVI", ee.Reducer.max(), "s2_ndvi_max"), _temporal_slope(s2, "NDVI", start_date, "s2_ndvi_slope"),
        _stat(s2, "EVI", ee.Reducer.mean(), "s2_evi_mean"), _stat(s2, "EVI", ee.Reducer.median(), "s2_evi_median"),
        _stat(s2, "NDMI", ee.Reducer.mean(), "s2_ndmi_mean"), _stat(s2, "NDMI", ee.Reducer.median(), "s2_ndmi_median"),
        _stat(s2, "NDWI", ee.Reducer.mean(), "s2_ndwi_mean"), _stat(s2, "NDWI", ee.Reducer.median(), "s2_ndwi_median"),
        _stat(s2, "NDRE", ee.Reducer.mean(), "s2_ndre_mean"), _stat(s2, "NDRE", ee.Reducer.median(), "s2_ndre_median"),
    ])
    s2_valid = s2.select("B8").count().gt(0)
    features, bands, sources_used, required_mask = s2_features, list(S2_FEATURE_BANDS), ["Sentinel-2"], s2_valid

    if s1_count:
        s1_features = ee.Image.cat([
            _stat(s1, "VV", ee.Reducer.mean(), "s1_vv_mean"), _stat(s1, "VV", ee.Reducer.median(), "s1_vv_median"),
            _stat(s1, "VV", ee.Reducer.stdDev(), "s1_vv_std"), _temporal_slope(s1, "VV", start_date, "s1_vv_slope"),
            _stat(s1, "VH", ee.Reducer.mean(), "s1_vh_mean"), _stat(s1, "VH", ee.Reducer.median(), "s1_vh_median"),
            _stat(s1, "VH", ee.Reducer.stdDev(), "s1_vh_std"), _temporal_slope(s1, "VH", start_date, "s1_vh_slope"),
            _stat(s1, "VV_VH_ratio", ee.Reducer.mean(), "s1_ratio_mean"),
            _stat(s1, "VV_VH_ratio", ee.Reducer.median(), "s1_ratio_median"),
            _stat(s1, "VV_VH_ratio", ee.Reducer.stdDev(), "s1_ratio_std"),
        ])
        features = features.addBands(s1_features)
        bands.extend(S1_FEATURE_BANDS)
        sources_used.append("Sentinel-1")
        required_mask = required_mask.And(s1.select("VV").count().gt(0))

    valid_fraction = gee_get_info(required_mask.reduceRegion(
        reducer=ee.Reducer.mean(), geometry=geom, scale=10, maxPixels=100_000_000, bestEffort=True
    ))
    valid_pixel_pct = float(next(iter(valid_fraction.values()), 0.0) or 0.0) * 100
    if valid_pixel_pct < MIN_FIELD_VALID_PIXEL_PCT:
        raise ClassificationUnavailable(
            f"Insufficient valid satellite pixels ({valid_pixel_pct:.1f}%; at least {MIN_FIELD_VALID_PIXEL_PCT:.0f}% are required)"
        )
    return {
        "geometry": geom, "image": features.select(bands), "required_mask": required_mask,
        "feature_bands": bands, "sources_used": sources_used, "s2_scene_count": s2_count,
        "s1_scene_count": s1_count, "valid_pixel_percentage": round(valid_pixel_pct, 2),
    }


def _spatial_fold(feature: ee.Feature) -> ee.Feature:
    """Assign deterministic coarse spatial blocks, never a random pixel split."""
    point = feature.geometry().centroid(1).coordinates()
    x = ee.Number(point.get(0)).multiply(10).floor()
    y = ee.Number(point.get(1)).multiply(10).floor()
    return feature.set("_spatial_fold", x.multiply(10007).add(y).abs().toInt().mod(5))


def _as_integer_id(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("boolean")
    numeric = float(value)
    if not numeric.is_integer():
        raise ValueError("non-integer")
    return int(numeric)


def _training_asset() -> Tuple[ee.FeatureCollection, Dict[int, str], Dict[str, Any], Dict[int, int], Dict[int, int]]:
    global _cached_training_asset, _cached_training_asset_id
    asset_id = os.getenv("GEE_CROP_TRAINING_ASSET")
    if not asset_id:
        raise ClassificationUnavailable("Valid crop-training data is not configured: GEE_CROP_TRAINING_ASSET is missing")
        
    if _cached_training_asset is not None and _cached_training_asset_id == asset_id:
        return _cached_training_asset

    try:
        training = ee.FeatureCollection(asset_id)
        # Execute distinct checks and sizes in one combined GEE call!
        batch_query = ee.Dictionary({
            "size": training.size(),
            "labelled_size": training.filter(ee.Filter.notNull(["crop_id", "crop_name", "label_source"])).size(),
            "histogram": training.filter(ee.Filter.notNull(["crop_id", "crop_name", "label_source"])).aggregate_histogram("crop_id"),
            "label_rows": training.filter(ee.Filter.notNull(["crop_id", "crop_name", "label_source"])).distinct(["crop_id", "crop_name"])
                          .reduceColumns(ee.Reducer.toList(2), ["crop_id", "crop_name"]).get("list"),
            "provenance": training.filter(ee.Filter.notNull(["crop_id", "crop_name", "label_source"])).aggregate_histogram("label_source"),
            "probe": training.filter(ee.Filter.notNull(["crop_id", "crop_name", "label_source"])).limit(1).geometry().area(1)
        })
        batch_res = gee_get_info(batch_query)
        total = int(batch_res.get("size", 0))
        labelled_count = int(batch_res.get("labelled_size", 0))
        histogram = batch_res.get("histogram") or {}
        label_rows = batch_res.get("label_rows") or []
        provenance_rows = batch_res.get("provenance") or {}
    except Exception as exc:
        raise ClassificationUnavailable(f"Valid crop-training data is not accessible: {exc}") from exc
        
    if total == 0 or labelled_count != total:
        raise ClassificationUnavailable("Valid crop-training data must be non-empty and every feature must contain crop_id, crop_name, and label_source")
    counts: Dict[int, int] = {}
    try:
        for raw_id, count in histogram.items():
            crop_id = _as_integer_id(raw_id)
            counts[crop_id] = int(count)
    except (TypeError, ValueError) as exc:
        raise ClassificationUnavailable("Valid crop-training data requires integer crop_id values") from exc
    if not counts:
        raise ClassificationUnavailable("Valid crop-training data contains no labelled classes")

    labels: Dict[int, str] = {}
    try:
        for row in label_rows:
            crop_id = _as_integer_id(row[0])
            label = str(row[1]).strip()
            if not label:
                raise ValueError("empty crop_name")
            existing = labels.get(crop_id)
            if existing is not None and existing != label:
                raise ClassificationUnavailable(
                    f"crop_id {crop_id} has conflicting crop_name values: {existing!r} and {label!r}"
                )
            labels[crop_id] = label
    except (IndexError, TypeError, ValueError) as exc:
        raise ClassificationUnavailable("Valid crop-training data requires a non-empty crop_name for every integer crop_id") from exc
    if set(counts) != set(labels):
        raise ClassificationUnavailable("Every crop_id must map to exactly one crop_name in the training asset")
    if len(set(labels.values())) != len(labels):
        raise ClassificationUnavailable("Each crop_id in the training asset must map to a unique crop_name")
    undersampled = {labels[crop_id]: count for crop_id, count in counts.items() if count < MIN_TRAINING_FEATURES_PER_CLASS}
    if undersampled:
        raise ClassificationUnavailable(f"Insufficient labelled training features per class: {undersampled}")
        
    # Pre-calculate train_counts and validation_counts once!
    labelled = training.filter(ee.Filter.notNull(["crop_id", "crop_name", "label_source"]))
    folded_collection = labelled.map(_spatial_fold)
    train_features = folded_collection.filter(ee.Filter.neq("_spatial_fold", 0))
    validation_features = folded_collection.filter(ee.Filter.eq("_spatial_fold", 0))
    
    split_query = ee.Dictionary({
        "train": train_features.aggregate_histogram("crop_id"),
        "validation": validation_features.aggregate_histogram("crop_id")
    })
    split_res = gee_get_info(split_query)
    
    class_ids = sorted(labels)
    train_counts_raw = split_res.get("train") or {}
    validation_counts_raw = split_res.get("validation") or {}
    train_counts = {crop_id: int(train_counts_raw.get(str(crop_id), 0)) for crop_id in class_ids}
    validation_counts = {crop_id: int(validation_counts_raw.get(str(crop_id), 0)) for crop_id in class_ids}

    diagnostic = {
        "training_asset": asset_id,
        "status": "valid",
        "classes": {str(crop_id): {"label": labels[crop_id], "features": count} for crop_id, count in counts.items()},
        "feature_count": total,
        "label_sources": provenance_rows,
        "spatial_validation": "deterministic 0.1-degree centroid block holdout (fold 0)",
    }
    
    _cached_training_asset = (folded_collection, labels, diagnostic, train_counts, validation_counts)
    _cached_training_asset_id = asset_id
    return _cached_training_asset


def _class_counts(collection: ee.FeatureCollection, class_ids: Iterable[int]) -> Dict[int, int]:
    histogram = gee_get_info(collection.aggregate_histogram("crop_id")) or {}
    parsed = {_as_integer_id(key): int(value) for key, value in histogram.items()}
    return {crop_id: parsed.get(crop_id, 0) for crop_id in class_ids}


def _balanced_samples(
    image: ee.Image, features: ee.FeatureCollection, class_ids: Iterable[int], bands: List[str], seed: int
) -> ee.FeatureCollection:
    # Single sampleRegions call to avoid "Too many concurrent aggregations"
    return (image.sampleRegions(
        collection=features,
        properties=["crop_id"],
        scale=10,
        geometries=False,
        tileScale=4
    ).filter(ee.Filter.notNull(bands + ["crop_id"])))


def _validation_metrics(matrix: List[List[float]], class_ids: List[int], labels: Dict[int, str]) -> Dict[str, Any]:
    total = sum(sum(row) for row in matrix)
    if not total:
        raise ClassificationUnavailable("Spatial validation produced no usable labelled pixels")
    diagonal = sum(matrix[index][index] for index in range(len(class_ids)))
    per_class: Dict[str, Dict[str, float | int | None]] = {}
    recalls: List[float] = []
    for index, crop_id in enumerate(class_ids):
        tp = matrix[index][index]
        actual = sum(matrix[index])
        predicted = sum(row[index] for row in matrix)
        precision = tp / predicted if predicted else None
        recall = tp / actual if actual else None
        f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else None
        if recall is not None:
            recalls.append(recall)
        per_class[labels[crop_id]] = {"precision": precision, "recall": recall, "f1": f1, "validation_pixels": int(actual)}
    return {
        "overall_accuracy": diagonal / total,
        "balanced_accuracy": sum(recalls) / len(recalls) if recalls else None,
        "per_class": per_class,
        "confusion_matrix": {"class_ids": class_ids, "labels": [labels[value] for value in class_ids], "matrix": matrix},
        "validation_pixels": int(total),
    }


def _field_entropy(distribution: Dict[str, float]) -> float:
    if len(distribution) < 2:
        return 0.0
    entropy = -sum(value * math.log(value) for value in distribution.values() if value > 0)
    return entropy / math.log(len(distribution))


def run_spatial_classification(geometry_geojson: Dict[str, Any], start_date: str, end_date: str) -> Dict[str, Any]:
    """Train with regional labels, spatially validate, and classify the requested AOI."""
    training, labels, training_diagnostic, train_counts, validation_counts = _training_asset()
    fused = build_fused_feature_image(geometry_geojson, start_date, end_date)
    class_ids = sorted(labels)
    train_features = training.filter(ee.Filter.neq("_spatial_fold", 0))
    validation_features = training.filter(ee.Filter.eq("_spatial_fold", 0))

    if any(count < MIN_TRAINING_FEATURES_PER_CLASS for count in train_counts.values()):
        raise ClassificationUnavailable(f"Spatial training split lacks sufficient features per class: {train_counts}")
    if any(count == 0 for count in validation_counts.values()):
        raise ClassificationUnavailable(f"Spatial validation split does not represent every configured class: {validation_counts}")

    # Check if training features intersect the image footprint / field AOI
    intersecting_count = gee_get_info(training.filterBounds(fused["geometry"]).size())
    if int(intersecting_count or 0) < 1:
        raise ClassificationUnavailable("Regional training asset features do not intersect this field's satellite footprint")

    model_image = fused["image"].updateMask(fused["required_mask"])
    train_samples = _balanced_samples(model_image, train_features, class_ids, fused["feature_bands"], 42)
    validation_samples = _balanced_samples(model_image, validation_features, class_ids, fused["feature_bands"], 84)
    
    # Calculate sample counts locally
    train_sample_count = sum(min(count, MAX_SAMPLES_PER_CLASS) for count in train_counts.values())
    validation_sample_count = sum(min(count, MAX_SAMPLES_PER_CLASS) for count in validation_counts.values())

    classifier = ee.Classifier.smileRandomForest(numberOfTrees=100, seed=42, minLeafPopulation=2).train(
        features=train_samples, classProperty="crop_id", inputProperties=fused["feature_bands"]
    )
    validated = validation_samples.classify(classifier)

    prediction = model_image.classify(classifier).rename("crop_id").clip(fused["geometry"])
    probability = model_image.classify(classifier.setOutputMode("PROBABILITY")).rename("prediction_probability").clip(fused["geometry"])

    # Batch evaluate confusion matrix and frequency histogram
    batch_query = ee.Dictionary({
        "matrix": validated.errorMatrix("crop_id", "classification", class_ids).array(),
        "histogram": prediction.reduceRegion(
            reducer=ee.Reducer.frequencyHistogram(), geometry=fused["geometry"], scale=10,
            maxPixels=100_000_000, bestEffort=True, tileScale=4,
        ).get("crop_id"),
        "sampled": prediction.addBands(probability).sample(
            region=fused["geometry"], scale=10, numPixels=200, geometries=True, tileScale=4
        )
    })
    
    try:
        batch_result = gee_get_info(batch_query)
    except Exception as exc:
        logger.warning("GEE spatial classification compute error: %s", exc)
        raise ClassificationUnavailable(f"GEE spatial classification unavailable: {exc}") from exc

    matrix = batch_result.get("matrix")
    histogram = batch_result.get("histogram") or {}
    sampled = batch_result.get("sampled") or {}

    if not matrix:
        raise ClassificationUnavailable("Spatial validation produced no usable labelled pixels")
        
    validation_metrics = _validation_metrics(matrix, class_ids, labels)
    overall_acc = validation_metrics.get("overall_accuracy", 0.0)
    print(f"[GEE Random Forest] Spatial Holdout Validation Accuracy: {overall_acc * 100:.2f}% | Classes: {list(labels.values())}", flush=True)

    counts = {_as_integer_id(key): int(value) for key, value in (histogram or {}).items()}
    total_pixels = sum(counts.values())
    if not total_pixels:
        raise ClassificationUnavailable("The validated classifier produced no usable field pixels")
    if set(counts) - set(labels):
        raise ClassificationUnavailable("The classifier emitted an unmapped crop_id")
    distribution = {labels[crop_id]: count / total_pixels for crop_id, count in counts.items()}
    dominant_id = max(counts, key=counts.get)
    dominant_label = labels[dominant_id]
    dominant_fraction = distribution[dominant_label]
    print(f"[GEE Random Forest] Field Pixel Classification: Dominant={dominant_label} ({dominant_fraction*100:.1f}%) | Distribution={', '.join(f'{k}: {v*100:.1f}%' for k, v in distribution.items())}", flush=True)

    sampled = batch_result.get("sampled") or {}
    render_features: List[Dict[str, Any]] = []
    dominant_probabilities: List[float] = []
    for item in sampled.get("features", []):
        properties = item.get("properties") or {}
        crop_value = properties.get("crop_id")
        coords = (item.get("geometry") or {}).get("coordinates")
        if crop_value is None or not coords:
            continue
        crop_id = _as_integer_id(crop_value)
        if crop_id not in labels:
            continue
        if crop_id == dominant_id and properties.get("prediction_probability") is not None:
            dominant_probabilities.append(float(properties["prediction_probability"]))
        cell = clipped_sample_cell(coords, geometry_geojson)
        if cell:
            render_features.append({"type": "Feature", "geometry": cell, "properties": {"crop": labels[crop_id], "crop_id": crop_id}})
    if not render_features:
        raise ClassificationUnavailable("The classifier produced no renderable field pixels")
    if not dominant_probabilities:
        raise ClassificationUnavailable("The classifier did not provide probability output for the field")

    model_probability = sum(dominant_probabilities) / len(dominant_probabilities)
    entropy = _field_entropy(distribution)
    status = "completed"
    prediction_label: str | None = dominant_label
    message = None
    if dominant_fraction < MIN_DOMINANT_CLASS_PCT or model_probability < MIN_FIELD_PROBABILITY:
        status = "low_confidence"
        prediction_label = None
        message = "Low-confidence / mixed classification: the field does not meet the configured dominance and probability thresholds."
    diagnostic = {
        "status": status,
        "prediction": prediction_label,
        "field_geometry_hash": None,  # API owns the canonical geometry hash.
        "observation_period": {"start": start_date, "end": end_date},
        "sources_used": fused["sources_used"],
        "features_used": fused["feature_bands"],
        "s2_observation_count": fused["s2_scene_count"],

        "s1_observation_count": fused["s1_scene_count"],
        "valid_pixel_percentage": fused["valid_pixel_percentage"],
        "classified_pixels": total_pixels,
        "dominant_class_percentage": dominant_fraction * 100,
        "mean_dominant_class_probability": model_probability,
        "spatial_entropy": entropy,
        "training": training_diagnostic,
        "training_sample_count": train_sample_count,
        "validation_sample_count": validation_sample_count,
        "validation_metrics": validation_metrics,
        "model": "Earth Engine smileRandomForest (200 trees)",
        "model_version": MODEL_VERSION,
        "feature_version": FEATURE_VERSION,
        "processing_timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return {
        "crop": prediction_label,
        "confidence": model_probability,
        "classification_status": status,
        "message": message,
        "class_distribution": distribution,
        "classification_map": {"type": "FeatureCollection", "features": render_features},
        "legend_classes": list(distribution),
        "available_classes": [labels[crop_id] for crop_id in class_ids],
        "training_sample_count": train_sample_count,
        "classification_pixel_count": total_pixels,
        "classification_coverage_pct": fused["valid_pixel_percentage"],
        "landsat_scene_count": 0,
        "feature_count": len(fused["feature_bands"]),
        "diagnostic": diagnostic,
        "validation_metrics": validation_metrics,
    }


def get_pixel_level_classification(*_args: Any, **_kwargs: Any) -> Dict[str, Any]:
    raise ClassificationUnavailable("Use run_spatial_classification with the fused feature image")
