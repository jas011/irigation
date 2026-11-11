import unittest

from app.services.analysis.crop_analysis_service import _fuse_crop_signals
from app.services.crop.crop_name_utils import normalize_crop_name


class CropFusionTests(unittest.TestCase):
    def test_normalize_paddy_rice_alias(self):
        self.assertEqual(normalize_crop_name("Paddy/Rice"), "Paddy")

    def test_fuse_prefers_agreement_between_sources(self):
        csv_signal = {"label": "Paddy", "confidence": 0.8, "source": "ground_truth_csv_overlap"}
        ml_signal = {"label": "Paddy", "confidence": 0.7, "source": "csv_trained_ml"}
        gee_signal = {"label": "Wheat", "confidence": 0.6, "source": "gee_rf"}
        label, confidence, sources = _fuse_crop_signals(csv_signal, ml_signal, gee_signal)
        self.assertEqual(label, "Paddy")
        self.assertGreater(confidence, 0.5)
        self.assertEqual(len(sources), 3)


if __name__ == "__main__":
    unittest.main()
