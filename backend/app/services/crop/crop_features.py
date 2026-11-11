import numpy as np
import logging
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger("agrisense.crop_features")

def calculate_slope(dates: List[str], values: List[float]) -> float:
    """
    Calculates the linear regression slope of values over time (in days since start).
    """
    if len(values) < 2:
        return 0.0
    try:
        dt0 = datetime.strptime(dates[0], "%Y-%m-%d")
        days = [(datetime.strptime(d, "%Y-%m-%d") - dt0).days for d in dates]
        slope, _ = np.polyfit(days, values, 1)
        return float(slope)
    except Exception as e:
        logger.warning(f"Error calculating temporal slope: {str(e)}")
        return 0.0

def extract_features(s2_obs: List[Dict[str, Any]], s1_obs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extracts summary statistics and temporal signatures from Sentinel-1 and Sentinel-2 observations.
    Used for crop classification and growth stage tracking.
    """
    features = {}
    
    # --- SENTINEL-2 INDICES FEATURES ---
    if s2_obs:
        ndvi_vals = [obs['NDVI'] for obs in s2_obs]
        evi_vals = [obs['EVI'] for obs in s2_obs]
        ndmi_vals = [obs['NDMI'] for obs in s2_obs]
        ndwi_vals = [obs['NDWI'] for obs in s2_obs]
        dates = [obs['date'] for obs in s2_obs]
        
        # NDVI statistics
        features['ndvi_max'] = float(np.max(ndvi_vals))
        features['ndvi_min'] = float(np.min(ndvi_vals))
        features['ndvi_mean'] = float(np.mean(ndvi_vals))
        features['ndvi_std'] = float(np.std(ndvi_vals))
        features['ndvi_amp'] = features['ndvi_max'] - features['ndvi_min']
        features['ndvi_slope'] = calculate_slope(dates, ndvi_vals)
        
        # Peak NDVI details
        peak_idx = np.argmax(ndvi_vals)
        features['ndvi_peak_value'] = float(ndvi_vals[peak_idx])
        features['ndvi_peak_date'] = dates[peak_idx]
        
        # EVI statistics
        features['evi_max'] = float(np.max(evi_vals))
        features['evi_min'] = float(np.min(evi_vals))
        features['evi_mean'] = float(np.mean(evi_vals))
        features['evi_slope'] = calculate_slope(dates, evi_vals)
        
        # NDMI (Moisture Index) statistics
        features['ndmi_max'] = float(np.max(ndmi_vals))
        features['ndmi_min'] = float(np.min(ndmi_vals))
        features['ndmi_mean'] = float(np.mean(ndmi_vals))
        features['ndmi_slope'] = calculate_slope(dates, ndmi_vals)
        
        # NDWI (Water Index) statistics
        features['ndwi_max'] = float(np.max(ndwi_vals))
        features['ndwi_min'] = float(np.min(ndwi_vals))
        features['ndwi_mean'] = float(np.mean(ndwi_vals))
        
        # Latest values (represent the current crop status)
        latest = s2_obs[-1]
        features['latest_ndvi'] = latest['NDVI']
        features['latest_evi'] = latest['EVI']
        features['latest_ndmi'] = latest['NDMI']
        features['latest_ndwi'] = latest['NDWI']
        features['latest_savi'] = latest.get('SAVI', 0.0)
        features['latest_gndvi'] = latest.get('GNDVI', 0.0)
    else:
        # Default fallback values if no Sentinel-2 observations
        for index in ['ndvi', 'evi', 'ndmi', 'ndwi']:
            features[f'{index}_max'] = 0.0
            features[f'{index}_min'] = 0.0
            features[f'{index}_mean'] = 0.0
            features[f'{index}_std'] = 0.0
            features[f'{index}_amp'] = 0.0
            features[f'{index}_slope'] = 0.0
        features['ndvi_peak_value'] = 0.0
        features['ndvi_peak_date'] = ""
        features['latest_ndvi'] = 0.0
        features['latest_evi'] = 0.0
        features['latest_ndmi'] = 0.0
        features['latest_ndwi'] = 0.0
        features['latest_savi'] = 0.0
        features['latest_gndvi'] = 0.0
        
    # --- SENTINEL-1 SAR FEATURES ---
    if s1_obs:
        vv_vals = [obs['VV'] for obs in s1_obs]
        vh_vals = [obs['VH'] for obs in s1_obs]
        ratio_vals = [obs['VV_VH_ratio'] for obs in s1_obs]
        dates_s1 = [obs['date'] for obs in s1_obs]
        
        features['s1_vv_mean'] = float(np.mean(vv_vals))
        features['s1_vh_mean'] = float(np.mean(vh_vals))
        features['s1_vv_std'] = float(np.std(vv_vals))
        features['s1_vh_std'] = float(np.std(vh_vals))
        features['s1_ratio_mean'] = float(np.mean(ratio_vals))
        features['s1_ratio_median'] = float(np.median(ratio_vals))
        features['s1_vv_slope'] = calculate_slope(dates_s1, vv_vals)
        features['s1_vh_slope'] = calculate_slope(dates_s1, vh_vals)
        
        # Latest values
        latest_s1 = s1_obs[-1]
        features['latest_vv'] = latest_s1['VV']
        features['latest_vh'] = latest_s1['VH']
        features['latest_vv_vh_ratio'] = latest_s1['VV_VH_ratio']
    else:
        # Fallbacks
        features['s1_vv_mean'] = 0.0
        features['s1_vh_mean'] = 0.0
        features['s1_vv_std'] = 0.0
        features['s1_vh_std'] = 0.0
        features['s1_ratio_mean'] = 1.0
        features['s1_ratio_median'] = 1.0
        features['s1_vv_slope'] = 0.0
        features['s1_vh_slope'] = 0.0
        features['latest_vv'] = 0.0
        features['latest_vh'] = 0.0
        features['latest_vv_vh_ratio'] = 1.0
        
    return features
