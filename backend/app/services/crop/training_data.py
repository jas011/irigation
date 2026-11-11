"""Validation rules shared by the crop-training CSV preflight and GEE model."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Any, Dict


REQUIRED_COLUMNS = {
    "geometry", "crop_id", "crop_name", "sample_id", "survey_date",
    "label_source", "label_confidence",
}


def is_synthetic_label(value: Any) -> bool:
    """Return whether a label provenance explicitly identifies demo/synthetic data."""
    normalized = str(value or "").strip().casefold()
    return "synthetic" in normalized or "demo" in normalized


def inspect_training_csv(path: str | Path) -> Dict[str, Any]:
    """Validate the supplied CSV before it is uploaded as a GEE table asset.

    This is intentionally a schema/provenance check, not a claim that the
    labels are ground truth.  The same provenance policy is enforced at GEE
    prediction time from the uploaded feature properties.
    """
    source = Path(path)
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing = sorted(REQUIRED_COLUMNS - columns)
        if missing:
            return {"valid": False, "errors": [f"Missing required columns: {', '.join(missing)}"]}

        class_names: Dict[str, str] = {}
        class_counts: Counter[str] = Counter()
        provenance: Counter[str] = Counter()
        errors: list[str] = []
        row_count = 0
        for row_number, row in enumerate(reader, start=2):
            row_count += 1
            crop_id = str(row.get("crop_id") or "").strip()
            crop_name = str(row.get("crop_name") or "").strip()
            if not crop_id or not crop_name:
                errors.append(f"Row {row_number}: crop_id and crop_name are required")
                continue
            try:
                if not float(crop_id).is_integer():
                    raise ValueError
            except ValueError:
                errors.append(f"Row {row_number}: crop_id must be an integer")
                continue
            prior = class_names.setdefault(crop_id, crop_name)
            if prior != crop_name:
                errors.append(f"Row {row_number}: crop_id {crop_id} maps to both {prior!r} and {crop_name!r}")
            class_counts[crop_id] += 1
            provenance[str(row.get("label_source") or "").strip()] += 1

    if row_count == 0:
        errors.append("The CSV has no data rows")
    if len(set(class_names.values())) != len(class_names):
        errors.append("Each crop_id must have a unique crop_name")
    synthetic_rows = sum(count for name, count in provenance.items() if is_synthetic_label(name))
    return {
        "valid": not errors and synthetic_rows == 0,
        "row_count": row_count,
        "class_count": len(class_names),
        "classes": {crop_id: {"crop_name": class_names[crop_id], "rows": class_counts[crop_id]} for crop_id in sorted(class_names, key=int)},
        "label_sources": dict(provenance),
        "synthetic_row_count": synthetic_rows,
        "errors": errors + (["Synthetic/demo labels cannot be used for an accuracy-backed production model"] if synthetic_rows else []),
    }
