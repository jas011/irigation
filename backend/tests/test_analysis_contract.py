import csv
import os
import tempfile
import unittest
from pathlib import Path

from app.services.analysis.ground_truth_service import GroundTruthService


class GroundTruthContractTests(unittest.TestCase):
    def test_ground_truth_raises_for_missing_configured_csv_path(self):
        original = os.environ.get("CROP_TRAINING_CSV_PATH")
        os.environ["CROP_TRAINING_CSV_PATH"] = "C:/definitely/missing/crop.csv"
        try:
            with self.assertRaises(FileNotFoundError):
                GroundTruthService.load_csv_data()
        finally:
            if original is None:
                os.environ.pop("CROP_TRAINING_CSV_PATH", None)
            else:
                os.environ["CROP_TRAINING_CSV_PATH"] = original

    def test_ground_truth_accepts_crop_name_without_crop_label_alias(self):
        handle = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
        with handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["geometry", "crop_id", "crop_name", "sample_id", "survey_date", "season", "sowing_date", "district", "state"],
            )
            writer.writeheader()
            writer.writerow({
                "geometry": "POLYGON((75.4 32.0, 75.5 32.0, 75.5 32.1, 75.4 32.1, 75.4 32.0))",
                "crop_id": "1",
                "crop_name": "Paddy/Rice",
                "sample_id": "PB-001",
                "survey_date": "2025-07-01",
                "season": "Kharif",
                "sowing_date": "2025-06-15",
                "district": "Gurdaspur",
                "state": "Punjab",
            })
        self.addCleanup(lambda: Path(handle.name).unlink(missing_ok=True))

        original = os.environ.get("CROP_TRAINING_CSV_PATH")
        os.environ["CROP_TRAINING_CSV_PATH"] = handle.name
        try:
            rows = GroundTruthService.load_csv_data()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["crop_label"], "Paddy/Rice")
        finally:
            if original is None:
                os.environ.pop("CROP_TRAINING_CSV_PATH", None)
            else:
                os.environ["CROP_TRAINING_CSV_PATH"] = original

    def test_ground_truth_predicts_nearest_when_aoi_has_no_overlap(self):
        geometry = {
            "type": "Polygon",
            "coordinates": [[
                [77.0, 30.0],
                [77.1, 30.0],
                [77.1, 30.1],
                [77.0, 30.1],
                [77.0, 30.0],
            ]],
        }

        prediction = GroundTruthService.predict_crop(geometry)
        self.assertIn("label", prediction)
        self.assertGreater(prediction["confidence"], 0.0)
        self.assertEqual(prediction["source"], "ground_truth_csv_nearest")
