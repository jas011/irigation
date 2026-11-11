"""Run before importing a crop-training CSV into Google Earth Engine."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.crop.training_data import inspect_training_csv


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a labelled crop-training CSV for GEE import")
    parser.add_argument("csv_path", type=Path)
    args = parser.parse_args()
    report = inspect_training_csv(args.csv_path)
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
