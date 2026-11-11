import csv
import tempfile
import unittest
from pathlib import Path

from app.services.crop.training_data import inspect_training_csv


class TrainingDataTests(unittest.TestCase):
    def write_csv(self, rows):
        handle = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8")
        with handle:
            writer = csv.DictWriter(handle, fieldnames=["geometry", "crop_id", "crop_name", "sample_id", "survey_date", "label_source", "label_confidence"])
            writer.writeheader()
            writer.writerows(rows)
        self.addCleanup(lambda: Path(handle.name).unlink(missing_ok=True))
        return handle.name

    def test_rejects_synthetic_demo_labels(self):
        path = self.write_csv([{"geometry": "POLYGON(...) ", "crop_id": "1", "crop_name": "Paddy", "sample_id": "x", "survey_date": "2025-07-01", "label_source": "Synthetic demo data", "label_confidence": "synthetic"}])
        report = inspect_training_csv(path)
        self.assertFalse(report["valid"])
        self.assertEqual(report["synthetic_row_count"], 1)

    def test_accepts_verified_consistent_labels(self):
        path = self.write_csv([{"geometry": "POLYGON(...) ", "crop_id": "1", "crop_name": "Paddy", "sample_id": "x", "survey_date": "2025-07-01", "label_source": "Punjab field survey 2025", "label_confidence": "verified"}])
        report = inspect_training_csv(path)
        self.assertTrue(report["valid"])
        self.assertEqual(report["class_count"], 1)
