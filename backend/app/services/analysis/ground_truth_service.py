import csv
import math
import os
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from shapely import wkt
from shapely.strtree import STRtree

from app.services.crop.crop_name_utils import normalize_crop_name


class GroundTruthValidationError(ValueError):
    pass


_LOADED_CACHE: Optional[Tuple[Path, float, List[Dict[str, Any]], STRtree, List[BaseGeometry]]] = None


class GroundTruthService:
    CSV_ENV_VAR = "CROP_TRAINING_CSV_PATH"
    REQUIRED_COLUMNS = {
        "geometry",
        "crop_id",
        "crop_name",
        "sowing_date",
        "season",
        "district",
        "state",
    }

    @staticmethod
    def default_csv_path() -> Path:
        backend_root = Path(__file__).resolve().parents[3]
        return backend_root / "data" / "punjab_gee_5000_advanced_records.csv"

    @classmethod
    def resolve_csv_path(cls) -> Path:
        configured = os.getenv(cls.CSV_ENV_VAR)
        if configured:
            candidate = Path(configured).expanduser()
            if candidate.is_file():
                return candidate
            raise FileNotFoundError(f"Configured CSV file not found: {configured}")

        candidate = cls.default_csv_path()
        if candidate.is_file():
            return candidate
        raise FileNotFoundError(f"Crop training CSV is missing. Expected at: {candidate}")

    @classmethod
    def load_csv_data(cls) -> List[Dict[str, Any]]:
        records, _, _ = cls._get_indexed_data()
        return records

    @classmethod
    def _get_indexed_data(cls) -> Tuple[List[Dict[str, Any]], STRtree, List[BaseGeometry]]:
        global _LOADED_CACHE
        csv_path = cls.resolve_csv_path()
        mtime = csv_path.stat().st_mtime

        if _LOADED_CACHE is not None:
            cached_path, cached_mtime, records, tree, geoms = _LOADED_CACHE
            if cached_path == csv_path and cached_mtime == mtime:
                return records, tree, geoms

        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise GroundTruthValidationError("CSV file is empty or missing a header row.")
            missing = sorted(cls.REQUIRED_COLUMNS - set(reader.fieldnames))
            if missing:
                raise GroundTruthValidationError(
                    f"CSV schema invalid. Missing required columns: {', '.join(missing)}"
                )

            rows: List[Dict[str, Any]] = []
            geoms: List[BaseGeometry] = []
            for row_number, row in enumerate(reader, start=2):
                normalized = {key: (value.strip() if isinstance(value, str) else value) for key, value in row.items()}
                if not normalized.get("crop_name") and normalized.get("crop_label"):
                    normalized["crop_name"] = normalized["crop_label"]
                if not normalized.get("crop_label") and normalized.get("crop_name"):
                    normalized["crop_label"] = normalized["crop_name"]
                if not normalized.get("crop_name"):
                    raise GroundTruthValidationError(f"CSV row {row_number} has no crop_name.")
                if not normalized.get("geometry"):
                    raise GroundTruthValidationError(f"CSV row {row_number} has no geometry data.")
                try:
                    geom = wkt.loads(normalized["geometry"])
                    if not geom.is_valid:
                        raise GroundTruthValidationError(f"CSV row {row_number} contains an invalid polygon geometry.")
                except Exception as exc:  # noqa: BLE001
                    raise GroundTruthValidationError(f"CSV row {row_number} has invalid polygon WKT: {exc}") from exc
                normalized["geometry_obj"] = geom
                rows.append(normalized)
                geoms.append(geom)

        if not rows:
            raise GroundTruthValidationError("CSV file contains no usable training records.")

        tree = STRtree(geoms)
        _LOADED_CACHE = (csv_path, mtime, rows, tree, geoms)
        print(f"[Ground Truth CSV] Loaded and spatial-indexed {len(rows)} reference records from {csv_path.name}.", flush=True)
        return rows, tree, geoms

    @staticmethod
    def _as_geometry(geometry: Any) -> BaseGeometry:
        if isinstance(geometry, str):
            try:
                return wkt.loads(geometry)
            except Exception as exc:  # noqa: BLE001
                raise ValueError(f"AOI geometry is invalid WKT: {exc}") from exc
        if isinstance(geometry, dict):
            try:
                return shape(geometry)
            except Exception as exc:  # noqa: BLE001
                raise ValueError(f"AOI GeoJSON is invalid: {exc}") from exc
        raise ValueError("AOI geometry must be GeoJSON or WKT.")

    @classmethod
    def find_relevant_records(cls, geometry: Any, limit: int = 20) -> List[Dict[str, Any]]:
        if geometry is None:
            raise ValueError("AOI geometry is required.")

        aoi = cls._as_geometry(geometry)
        if aoi.is_empty:
            raise ValueError("AOI polygon is empty.")

        records, tree, _ = cls._get_indexed_data()
        intersecting_indices = tree.query(aoi, predicate="intersects")
        if len(intersecting_indices) == 0:
            return []

        candidates = [records[idx] for idx in intersecting_indices]
        candidates.sort(
            key=lambda item: item["geometry_obj"].intersection(aoi).area,
            reverse=True,
        )
        return candidates[:limit]

    @classmethod
    def find_nearest_records(cls, geometry: Any, limit: int = 10) -> List[Dict[str, Any]]:
        aoi = cls._as_geometry(geometry)
        records, tree, _ = cls._get_indexed_data()
        nearest_indices = tree.query(aoi, predicate="dwithin", distance=0.5)
        if len(nearest_indices) == 0:
            centroid = aoi.centroid
            ranked = sorted(
                records,
                key=lambda r: math.hypot(centroid.x - r["geometry_obj"].centroid.x, centroid.y - r["geometry_obj"].centroid.y)
            )
            return ranked[:limit]

        centroid = aoi.centroid
        candidates = [records[idx] for idx in nearest_indices]
        candidates.sort(
            key=lambda r: math.hypot(centroid.x - r["geometry_obj"].centroid.x, centroid.y - r["geometry_obj"].centroid.y)
        )
        return candidates[:limit]

    @classmethod
    def predict_crop(cls, geometry: Any) -> Dict[str, Any]:
        """Return a crop prediction from CSV overlap or nearest-neighbour records."""
        aoi = cls._as_geometry(geometry)
        overlapping = cls.find_relevant_records(geometry, limit=20)
        if overlapping:
            crop_names = [normalize_crop_name(record.get("crop_name")) for record in overlapping]
            crop_label, frequency = Counter(crop_names).most_common(1)[0]
            selected = next(record for record in overlapping if normalize_crop_name(record.get("crop_name")) == crop_label)
            overlap_area = sum(
                record["geometry_obj"].intersection(aoi).area
                for record in overlapping
                if record["geometry_obj"].intersects(aoi)
            )
            confidence = min(0.95, round((frequency / max(len(overlapping), 1)) * 0.35 + 0.55, 3))
            print(f"[Ground Truth CSV] Matched {len(overlapping)} overlapping records in AOI -> Dominant: {crop_label} (Confidence: {confidence:.2f})", flush=True)
            return {
                "label": crop_label,
                "confidence": confidence,
                "source": "ground_truth_csv_overlap",
                "matched_records": len(overlapping),
                "season": selected.get("season"),
                "sowing_date": selected.get("sowing_date"),
                "overlap_area": overlap_area,
            }

        nearest = cls.find_nearest_records(geometry, limit=12)
        if not nearest:
            return {
                "label": "Unknown",
                "confidence": 0.0,
                "source": "ground_truth_csv_none",
                "matched_records": 0,
                "season": None,
                "sowing_date": None,
            }

        crop_names = [normalize_crop_name(record.get("crop_name")) for record in nearest]
        crop_label, frequency = Counter(crop_names).most_common(1)[0]
        selected = next(record for record in nearest if normalize_crop_name(record.get("crop_name")) == crop_label)
        centroid = aoi.centroid
        nearest_distance = min(
            math.hypot(centroid.x - record["geometry_obj"].centroid.x, centroid.y - record["geometry_obj"].centroid.y)
            for record in nearest
        )
        distance_penalty = min(0.35, nearest_distance * 4.0)
        confidence = max(0.35, round((frequency / max(len(nearest), 1)) * 0.4 + 0.45 - distance_penalty, 3))
        print(f"[Ground Truth CSV] Found {len(nearest)} nearest reference fields (Distance: {nearest_distance:.4f}°) -> {crop_label} (Confidence: {confidence:.2f})", flush=True)
        return {
            "label": crop_label,
            "confidence": confidence,
            "source": "ground_truth_csv_nearest",
            "matched_records": len(nearest),
            "season": selected.get("season"),
            "sowing_date": selected.get("sowing_date"),
            "nearest_distance_deg": round(nearest_distance, 4),
        }

