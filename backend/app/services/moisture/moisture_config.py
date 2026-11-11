# Moisture Stress Model Configurations

STRESS_THRESHOLDS = {
    "No Stress": (0, 20),
    "Low Stress": (20, 40),
    "Moderate Stress": (40, 60),
    "High Stress": (60, 80),
    "Severe Stress": (80, 100)
}

# Feature weights used to calculate the final combined stress score (0 to 100).
# Must sum to 1.0. If Landsat LST is unavailable, LST weight will be redistributed
# dynamically to other optical indices.
DEFAULT_WEIGHTS = {
    "ndmi": 0.40,
    "vci": 0.30,
    "ndwi": 0.15,
    "sar": 0.15
}

WEIGHTS_WITH_LST = {
    "ndmi": 0.30,
    "vci": 0.20,
    "ndwi": 0.15,
    "sar": 0.15,
    "lst": 0.20
}

# Heuristic boundary mappings for individual indices to map them to a 0-100 stress scale
# (0 = wet/optimal, 100 = dry/severe stress)
INDEX_BOUNDARIES = {
    "ndmi": {
        "wet_limit": 0.35,  # NDMI >= 0.35 represents 0 stress
        "dry_limit": -0.05  # NDMI <= -0.05 represents 100 stress
    },
    "ndwi": {
        "wet_limit": -0.10, # NDWI >= -0.10 represents 0 stress (for vegetation NDWI)
        "dry_limit": -0.55  # NDWI <= -0.55 represents 100 stress
    },
    "lst": {
        "cool_limit": 26.0, # Celsius or below is 0 stress
        "hot_limit": 38.0   # Celsius or above is 100 stress
    }
}
