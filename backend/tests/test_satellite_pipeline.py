import unittest
from app.services.crop.crop_features import extract_features
from app.services.crop.growth_stage_service import detect_growth_stage
from app.services.moisture.moisture_stress_service import calculate_stress_from_features, calculate_stress_trends

class TestSatellitePipeline(unittest.TestCase):

    def setUp(self):
        # Create standard mock Sentinel-2 observations
        self.mock_s2 = [
            {"date": "2026-05-10", "NDVI": 0.18, "EVI": 0.12, "NDMI": -0.05, "NDWI": 0.15, "SAVI": 0.12, "GNDVI": 0.18},
            {"date": "2026-05-25", "NDVI": 0.22, "EVI": 0.15, "NDMI": 0.05, "NDWI": -0.10, "SAVI": 0.15, "GNDVI": 0.22},
            {"date": "2026-06-15", "NDVI": 0.45, "EVI": 0.32, "NDMI": 0.25, "NDWI": -0.30, "SAVI": 0.35, "GNDVI": 0.45},
            {"date": "2026-07-05", "NDVI": 0.65, "EVI": 0.48, "NDMI": 0.38, "NDWI": -0.45, "SAVI": 0.50, "GNDVI": 0.65},
            {"date": "2026-07-25", "NDVI": 0.78, "EVI": 0.58, "NDMI": 0.42, "NDWI": -0.52, "SAVI": 0.60, "GNDVI": 0.78},
            {"date": "2026-08-10", "NDVI": 0.76, "EVI": 0.56, "NDMI": 0.40, "NDWI": -0.50, "SAVI": 0.58, "GNDVI": 0.76}
        ]
        
        # Create standard mock Sentinel-1 observations
        self.mock_s1 = [
            {"date": "2026-05-12", "orbit": "ASCENDING", "VV": -14.2, "VH": -21.5, "VV_VH_ratio": 5.4, "VV_VH_diff": 7.3},
            {"date": "2026-06-14", "orbit": "ASCENDING", "VV": -12.5, "VH": -19.2, "VV_VH_ratio": 4.7, "VV_VH_diff": 6.7},
            {"date": "2026-07-26", "orbit": "ASCENDING", "VV": -9.8, "VH": -15.4, "VV_VH_ratio": 3.6, "VV_VH_diff": 5.6}
        ]

    def test_feature_extraction(self):
        """Test biophysical feature extraction calculations."""
        features = extract_features(self.mock_s2, self.mock_s1)
        
        self.assertIn("ndvi_max", features)
        self.assertIn("ndvi_min", features)
        self.assertIn("ndvi_slope", features)
        self.assertIn("latest_ndvi", features)
        self.assertIn("s1_vv_mean", features)
        
        self.assertEqual(features["ndvi_max"], 0.78)
        self.assertEqual(features["ndvi_min"], 0.18)
        self.assertEqual(features["latest_ndvi"], 0.76)
        self.assertGreater(features["ndvi_slope"], 0.0)  # greening slope

    def test_growth_stage_detection(self):
        """Test growth stage classification heuristics."""
        stage_data = detect_growth_stage("Paddy", self.mock_s2, self.mock_s1)
        
        self.assertIn("stage", stage_data)
        self.assertIn("confidence", stage_data)
        self.assertIn("evidence", stage_data)
        self.assertIn("days_since_sowing", stage_data)
        
        self.assertGreater(stage_data["days_since_sowing"], 0)
        # Should be in late flowering or grain filling since age is around 90 days and NDVI is peaking
        self.assertIn(stage_data["stage"], ["Flowering", "Grain Filling"])

    def test_moisture_stress_calculations(self):
        """Test moisture stress calculations, normalization, and trends."""
        features = extract_features(self.mock_s2, self.mock_s1)
        
        score, stress_class, breakdown = calculate_stress_from_features(features, has_lst=False)
        
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)
        self.assertIn(stress_class, ["No Stress", "Low Stress", "Moderate Stress", "High Stress", "Severe Stress"])
        self.assertIn("ndmi_stress", breakdown)
        
        # Test trend series
        trends = calculate_stress_trends(self.mock_s2)
        self.assertEqual(len(trends), len(self.mock_s2))
        self.assertEqual(trends[0]["date"], "2026-05-10")

if __name__ == '__main__':
    unittest.main()
