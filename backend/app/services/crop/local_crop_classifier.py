"""Sklearn crop classifier trained from Punjab CSV ground-truth records."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Dict

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

from app.services.analysis.ground_truth_service import GroundTruthService
from app.services.crop.crop_name_utils import normalize_crop_name

logger = logging.getLogger("agrisense.local_crop_classifier")

SEASON_CODES = {"kharif": 0.0, "rabi": 1.0, "zaid": 2.0}


def _season_code(season: str | None) -> float:
    return SEASON_CODES.get((season or "Kharif").strip().casefold(), 2.0)


def _geometry_centroid(geometry: Any) -> tuple[float, float]:
    geom = GroundTruthService._as_geometry(geometry)
    centroid = geom.centroid
    return float(centroid.x), float(centroid.y)


@lru_cache(maxsize=1)
def _load_model() -> tuple[RandomForestClassifier, LabelEncoder]:
    records = GroundTruthService.load_csv_data()
    features: list[list[float]] = []
    labels: list[str] = []

    for record in records:
        centroid = record["geometry_obj"].centroid
        features.append([
            float(centroid.x),
            float(centroid.y),
            _season_code(record.get("season")),
        ])
        labels.append(normalize_crop_name(record.get("crop_name")))

    label_encoder = LabelEncoder()
    encoded_labels = label_encoder.fit_transform(labels)
    model = RandomForestClassifier(
        n_estimators=200,
        random_state=42,
        min_samples_leaf=2,
        class_weight="balanced_subsample",
    )
    model.fit(np.asarray(features, dtype=float), encoded_labels)
    logger.info(
        "Loaded CSV-trained crop model with %s records and %s classes.",
        len(labels),
        len(label_encoder.classes_),
    )
    return model, label_encoder


class CsvTrainedCropModel:
    @classmethod
    def predict(cls, geometry: Any, *, season: str | None = None) -> Dict[str, Any]:
        model, label_encoder = _load_model()
        lon, lat = _geometry_centroid(geometry)
        vector = np.asarray([[lon, lat, _season_code(season)]], dtype=float)
        probabilities = model.predict_proba(vector)[0]
        best_index = int(np.argmax(probabilities))
        label = str(label_encoder.inverse_transform([best_index])[0])
        confidence = float(probabilities[best_index])
        distribution = {
            str(label_encoder.inverse_transform([index])[0]): float(prob)
            for index, prob in enumerate(probabilities)
        }
        return {
            "label": label,
            "confidence": round(confidence, 3),
            "source": "csv_trained_ml",
            "probabilities": distribution,
        }
