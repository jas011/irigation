import unittest
import asyncio
from typing import Dict, Any, List
from unittest.mock import patch, MagicMock

from app.schemas.field import GeoJSONPolygon
from app.services.field_validation_service import FieldValidationService
from app.services.crop.crop_features import extract_features
from app.services.crop.growth_stage_service import detect_growth_stage
from app.services.crop.crop_classification_service import _field_entropy
from app.services.analysis.crop_analysis_service import (
    _evaluate_phenological_crop_signal,
    _fuse_crop_signals,
    CropAnalysisService,
)
from app.services.moisture.moisture_stress_service import (
    calculate_index_stress,
    determine_stress_class,
    calculate_stress_from_features,
    calculate_stress_trends,
)
from app.services.analysis.moisture_analysis_service import MoistureAnalysisService
from app.services.analysis.ground_truth_service import GroundTruthService


class TestStage1FieldValidation(unittest.TestCase):
    def test_coordinate_format_checks(self):
        # Empty coords
        valid, msg = FieldValidationService.check_coordinates_format([])
        self.assertFalse(valid)

        # Non-closed polygon
        open_coords = [[[75.4, 31.4], [75.5, 31.4], [75.5, 31.5], [75.4, 31.5]]]
        valid, msg = FieldValidationService.check_coordinates_format(open_coords)
        self.assertFalse(valid)
        self.assertIn("closed", msg)

        # Valid closed polygon
        closed_coords = [[[75.4, 31.4], [75.5, 31.4], [75.5, 31.5], [75.4, 31.5], [75.4, 31.4]]]
        valid, msg = FieldValidationService.check_coordinates_format(closed_coords)
        self.assertTrue(valid)

    def test_field_validation_standalone(self):
        geometry = GeoJSONPolygon(
            type="Polygon",
            coordinates=[[[75.4000, 31.4000], [75.4050, 31.4000], [75.4050, 31.4050], [75.4000, 31.4050], [75.4000, 31.4000]]]
        )
        mock_db = MagicMock()
        # Mock PostGIS failure to test robust geodesic fallback
        mock_db.execute.side_effect = Exception("No PostGIS")
        
        res = FieldValidationService.validate_field(mock_db, geometry)
        self.assertTrue(res.valid)
        self.assertTrue(res.geometry_valid)
        self.assertTrue(res.area_valid)
        self.assertGreater(res.area_hectares, 0.0)
        self.assertGreater(res.area_acres, 0.0)
        self.assertGreater(res.perimeter_m, 0.0)
        self.assertAlmostEqual(res.centroid.longitude, 75.4025, places=2)
        self.assertAlmostEqual(res.centroid.latitude, 31.4025, places=2)


class TestStage2CropClassification(unittest.TestCase):
    def test_paddy_phenological_recognition(self):
        # Paddy Kharif sequence: early flood (NDWI > 0, low NDVI), peak NDVI in Aug-Sept > 0.65
        s2_paddy = [
            {"date": "2026-06-10", "NDVI": 0.15, "EVI": 0.10, "NDMI": 0.25, "NDWI": 0.10},
            {"date": "2026-06-25", "NDVI": 0.28, "EVI": 0.18, "NDMI": 0.20, "NDWI": -0.05},
            {"date": "2026-07-20", "NDVI": 0.55, "EVI": 0.40, "NDMI": 0.35, "NDWI": -0.30},
            {"date": "2026-08-25", "NDVI": 0.78, "EVI": 0.60, "NDMI": 0.42, "NDWI": -0.45},
            {"date": "2026-09-20", "NDVI": 0.72, "EVI": 0.52, "NDMI": 0.38, "NDWI": -0.40},
            {"date": "2026-10-15", "NDVI": 0.35, "EVI": 0.22, "NDMI": 0.12, "NDWI": -0.20},
        ]
        s1_paddy = [
            {"date": "2026-06-12", "VV": -15.0, "VH": -22.0, "VV_VH_ratio": 5.0},
            {"date": "2026-08-26", "VV": -9.5, "VH": -15.0, "VV_VH_ratio": 3.5},
        ]
        features = extract_features(s2_paddy, s1_paddy)
        signal = _evaluate_phenological_crop_signal(features, s2_paddy, s1_paddy)
        self.assertIsNotNone(signal)
        self.assertEqual(signal["label"], "Paddy")
        self.assertGreaterEqual(signal["confidence"], 0.75)

        # Growth stage
        stage = detect_growth_stage("Paddy", s2_paddy, s1_paddy)
        self.assertIn("stage", stage)
        self.assertGreater(stage["days_since_sowing"], 0)

    def test_wheat_phenological_recognition(self):
        # Wheat Rabi sequence: Sowing Nov/Dec, peak in Feb/Mar, harvest April
        s2_wheat = [
            {"date": "2025-11-20", "NDVI": 0.18, "EVI": 0.12, "NDMI": 0.05, "NDWI": -0.10},
            {"date": "2025-12-25", "NDVI": 0.35, "EVI": 0.25, "NDMI": 0.15, "NDWI": -0.20},
            {"date": "2026-01-20", "NDVI": 0.58, "EVI": 0.45, "NDMI": 0.28, "NDWI": -0.35},
            {"date": "2026-02-25", "NDVI": 0.82, "EVI": 0.65, "NDMI": 0.38, "NDWI": -0.48},
            {"date": "2026-03-20", "NDVI": 0.75, "EVI": 0.55, "NDMI": 0.30, "NDWI": -0.42},
            {"date": "2026-04-15", "NDVI": 0.25, "EVI": 0.15, "NDMI": 0.08, "NDWI": -0.15},
        ]
        features = extract_features(s2_wheat, [])
        signal = _evaluate_phenological_crop_signal(features, s2_wheat, [])
        self.assertIsNotNone(signal)
        self.assertEqual(signal["label"], "Wheat")
        self.assertGreaterEqual(signal["confidence"], 0.80)

    def test_bare_soil_and_water_recognition(self):
        # Bare soil: persistent low NDVI
        s2_soil = [
            {"date": "2026-05-10", "NDVI": 0.12, "EVI": 0.08, "NDMI": -0.10, "NDWI": -0.15},
            {"date": "2026-06-15", "NDVI": 0.14, "EVI": 0.09, "NDMI": -0.08, "NDWI": -0.12},
            {"date": "2026-07-20", "NDVI": 0.15, "EVI": 0.10, "NDMI": -0.05, "NDWI": -0.10},
        ]
        features_soil = extract_features(s2_soil, [])
        signal_soil = _evaluate_phenological_crop_signal(features_soil, s2_soil, [])
        self.assertIsNotNone(signal_soil)
        self.assertEqual(signal_soil["label"], "Bare Soil")

        # Water: positive NDWI, low NDVI
        s2_water = [
            {"date": "2026-05-10", "NDVI": -0.05, "EVI": -0.02, "NDMI": 0.30, "NDWI": 0.25},
            {"date": "2026-06-15", "NDVI": -0.02, "EVI": -0.01, "NDMI": 0.28, "NDWI": 0.22},
            {"date": "2026-07-20", "NDVI": -0.04, "EVI": -0.02, "NDMI": 0.29, "NDWI": 0.24},
        ]
        features_water = extract_features(s2_water, [])
        signal_water = _evaluate_phenological_crop_signal(features_water, s2_water, [])
        self.assertIsNotNone(signal_water)
        self.assertEqual(signal_water["label"], "Water")

    def test_insufficient_data_protection(self):
        # Empty or single observation should never fabricate a crop label
        res = CropAnalysisService._insufficient_data_response(
            {"type": "Polygon", "coordinates": []},
            "2026-05-01",
            "2026-08-01",
            s2_count=1,
            gee_status="ready",
            bhoonidhi_status="available",
        )
        self.assertEqual(res["cropPrediction"]["label"], "Insufficient Data")
        self.assertEqual(res["cropPrediction"]["confidence"], 0.0)
        self.assertEqual(res["dataQuality"], "Poor")
        self.assertEqual(res["growthStage"]["stage"], "Unknown")


class TestStage3MoistureStress(unittest.TestCase):
    def test_healthy_no_stress_condition(self):
        features = {
            "latest_ndmi": 0.40,      # Well hydrated (> 0.35)
            "latest_ndwi": 0.05,      # Optimal moisture
            "latest_ndvi": 0.78,
            "ndvi_max": 0.80,
            "ndvi_min": 0.20,
            "latest_vv_vh_ratio": 6.5, # Good SAR dielectric moisture
            "latest_lst": 24.0,       # Cool thermal (< 26°C)
        }
        score, stress_class, breakdown = calculate_stress_from_features(features, has_lst=True, has_s1=True)
        self.assertLessEqual(score, 20.0)
        self.assertEqual(stress_class, "No Stress")

    def test_severe_stress_condition(self):
        features = {
            "latest_ndmi": -0.15,     # Severely dry leaf moisture (< -0.05)
            "latest_ndwi": -0.65,     # Highly negative water index
            "latest_ndvi": 0.22,
            "ndvi_max": 0.80,
            "ndvi_min": 0.20,         # VCI close to 0 -> high VCI stress
            "latest_vv_vh_ratio": 2.5, # Very dry backscatter
            "latest_lst": 42.0,       # Extreme thermal heat stress (> 38°C)
        }
        score, stress_class, breakdown = calculate_stress_from_features(features, has_lst=True, has_s1=True)
        self.assertGreaterEqual(score, 80.0)
        self.assertEqual(stress_class, "Severe Stress")

    def test_stress_trends_generation(self):
        s2_obs = [
            {"date": "2026-05-10", "NDVI": 0.70, "EVI": 0.50, "NDMI": 0.35, "NDWI": -0.10},
            {"date": "2026-06-10", "NDVI": 0.65, "EVI": 0.45, "NDMI": 0.20, "NDWI": -0.25},
            {"date": "2026-07-10", "NDVI": 0.45, "EVI": 0.30, "NDMI": 0.05, "NDWI": -0.40},
        ]
        trends = calculate_stress_trends(s2_obs)
        self.assertEqual(len(trends), 3)
        # Stress score should increase as NDMI drops from 0.35 to 0.05
        self.assertLess(trends[0]["stress_score"], trends[2]["stress_score"])


class TestGroundTruthIndexing(unittest.TestCase):
    def test_spatial_strtree_query(self):
        # Bounding box near Amritsar/Punjab
        aoi = {
            "type": "Polygon",
            "coordinates": [[[74.85, 31.60], [74.90, 31.60], [74.90, 31.65], [74.85, 31.65], [74.85, 31.60]]]
        }
        records = GroundTruthService.find_nearest_records(aoi, limit=5)
        self.assertGreater(len(records), 0)
        self.assertIn("crop_name", records[0])
        self.assertIn("district", records[0])


if __name__ == "__main__":
    unittest.main()
