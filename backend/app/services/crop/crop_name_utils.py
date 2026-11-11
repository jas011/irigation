"""Shared crop label normalization for classification and growth-stage rules."""

from __future__ import annotations

CROP_NAME_ALIASES: dict[str, str] = {
    "paddy/rice": "Paddy",
    "paddy": "Paddy",
    "rice": "Paddy",
    "wheat": "Wheat",
    "cotton": "Cotton",
    "maize": "Maize",
    "corn": "Maize",
    "sugarcane": "Sugarcane",
    "other crop": "Other Crop",
    "non-crop": "Non-Crop",
    "bare soil": "Bare Soil",
    "water": "Water",
}


def normalize_crop_name(name: str | None) -> str:
    if not name:
        return "Other Crop"
    cleaned = str(name).strip()
    if not cleaned:
        return "Other Crop"
    mapped = CROP_NAME_ALIASES.get(cleaned.casefold())
    return mapped or cleaned
