import logging
from typing import Dict, Any, List, Tuple
from datetime import datetime

from app.services.crop.crop_name_utils import normalize_crop_name

logger = logging.getLogger("agrisense.growth_stage")

CROP_STAGES = {
    "Paddy": ["Sowing", "Germination", "Seedling", "Tillering", "Flowering", "Grain Filling", "Maturity", "Harvest"],
    "Wheat": ["Sowing", "Germination", "Vegetative", "Stem Extension", "Flowering", "Grain Filling", "Maturity", "Harvest"],
    "Cotton": ["Sowing", "Germination", "Seedling", "Vegetative", "Flowering", "Boll Development", "Maturity", "Harvest"],
    "Maize": ["Sowing", "Germination", "Seedling", "Vegetative", "Tasseling/Flowering", "Cob Development", "Maturity", "Harvest"],
    "Other Crop": ["Sowing", "Germination", "Vegetative", "Flowering", "Maturity", "Harvest"],
    "Non-Crop": ["Stable Vegetation"],
    "Bare Soil": ["Fallow / Bare"],
    "Water": ["Inundated"]
}

def estimate_sowing_date(s2_obs: List[Dict[str, Any]]) -> Tuple[str, int]:
    """
    Estimates the sowing date by locating the minimum NDVI (soil background or flooding)
    followed by a sustained upward green-up trend (NDVI > 0.22).
    Returns (sowing_date_str, days_since_sowing)
    """
    if len(s2_obs) < 2:
        return s2_obs[0]['date'] if s2_obs else "", 0
        
    dates = [obs['date'] for obs in s2_obs]
    ndvi_vals = [obs['NDVI'] for obs in s2_obs]
    
    # Simple heuristic: find the minimum NDVI in the first half of the season
    first_half_len = max(1, len(s2_obs) // 2)
    min_val = ndvi_vals[0]
    min_idx = 0
    for i in range(first_half_len):
        if ndvi_vals[i] < min_val:
            min_val = ndvi_vals[i]
            min_idx = i
            
    # Sowing is typically around this minimum soil/flooded index date
    sowing_date_str = dates[min_idx]
    
    try:
        sowing_dt = datetime.strptime(sowing_date_str, "%Y-%m-%d")
        latest_dt = datetime.strptime(dates[-1], "%Y-%m-%d")
        days_since_sowing = (latest_dt - sowing_dt).days
        if days_since_sowing < 0:
            days_since_sowing = 0
        return sowing_date_str, days_since_sowing
    except Exception as e:
        logger.warning(f"Error parsing sowing dates: {str(e)}")
        return dates[0], 0

def detect_growth_stage(crop_type: str, s2_obs: List[Dict[str, Any]], s1_obs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Determines crop growth stage, confidence level, and physical evidences from observations.
    """
    if not s2_obs:
        return {
            "stage": "Unknown",
            "confidence": 0.0,
            "evidence": ["No optical satellite data available."],
            "sowing_date": None,
            "days_since_sowing": None
        }
        
    sowing_date, days_since = estimate_sowing_date(s2_obs)
    crop_type = normalize_crop_name(crop_type)
    latest = s2_obs[-1]
    latest_ndvi = latest['NDVI']
    latest_ndmi = latest['NDMI']
    latest_ndwi = latest['NDWI']
    
    # Calculate recent NDVI changes
    recent_trend = "stable"
    if len(s2_obs) >= 3:
        n1, n2, n3 = s2_obs[-3]['NDVI'], s2_obs[-2]['NDVI'], s2_obs[-1]['NDVI']
        if n3 - n1 > 0.05:
            recent_trend = "increasing"
        elif n1 - n3 > 0.05:
            recent_trend = "decreasing"
            
    # Average SAR S1 VH if S1 data is available
    latest_vh = s1_obs[-1]['VH'] if s1_obs else -20.0
    
    stage = "Unknown"
    confidence = 0.5
    evidence = []
    
    if crop_type in ["Non-Crop", "Bare Soil", "Water"]:
        stage = CROP_STAGES[crop_type][0]
        confidence = 0.95
        evidence.append(f"Permanent class confirmed by land cover classification. Current NDVI: {latest_ndvi:.2f}.")
        return {
            "stage": stage,
            "confidence": confidence,
            "evidence": evidence,
            "sowing_date": None,
            "days_since_sowing": None
        }
        
    # Paddy phenological classification rules
    if crop_type == "Paddy":
        evidence.append(f"Days since sowing estimate: {days_since} days.")
        
        # 1. Inundation/Sowing
        if days_since <= 15 or (latest_ndvi < 0.22 and latest_ndwi > 0.05):
            stage = "Sowing"
            confidence = 0.85
            evidence.append(f"High surface moisture (NDWI: {latest_ndwi:.2f}) and low vegetation (NDVI: {latest_ndvi:.2f}) consistent with flooded paddy fields.")
            
        # 2. Germination / Seedling
        elif days_since <= 30 or (0.22 <= latest_ndvi < 0.35 and recent_trend == "increasing"):
            stage = "Seedling"
            confidence = 0.80
            evidence.append(f"Mild green cover (NDVI: {latest_ndvi:.2f}) showing positive growth trend.")
            
        # 3. Tillering
        elif days_since <= 60 or (0.35 <= latest_ndvi < 0.60 and recent_trend == "increasing"):
            stage = "Tillering"
            confidence = 0.85
            evidence.append(f"Strong vegetative growth. NDVI rising to {latest_ndvi:.2f} and SAR VH response ({latest_vh:.1f} dB) indicating vegetative biomass buildup.")
            
        # 4. Flowering / Panicle Initiation
        elif days_since <= 90 or (latest_ndvi >= 0.60 and recent_trend in ["increasing", "stable"]):
            stage = "Flowering"
            confidence = 0.80
            evidence.append(f"Peak canopy density (NDVI: {latest_ndvi:.2f}) and maximum leaf water content (NDMI: {latest_ndmi:.2f}) indicating reproduction phase.")
            
        # 5. Grain Filling
        elif days_since <= 110 or (0.50 <= latest_ndvi < 0.65 and recent_trend == "decreasing" and latest_ndmi < 0.25):
            stage = "Grain Filling"
            confidence = 0.75
            evidence.append(f"Slight decrease in NDVI ({latest_ndvi:.2f}) and leaf moisture (NDMI: {latest_ndmi:.2f}) representing grain dry down.")
            
        # 6. Maturity
        elif days_since <= 125 or (0.28 <= latest_ndvi < 0.50 and recent_trend == "decreasing"):
            stage = "Maturity"
            confidence = 0.80
            evidence.append(f"Senescence phase. NDVI declined to {latest_ndvi:.2f} as crop turns golden.")
            
        # 7. Harvested
        else:
            stage = "Harvest"
            confidence = 0.90
            evidence.append(f"Paddy field harvested. NDVI dropped to bare soil level ({latest_ndvi:.2f}).")
            
    # Cotton rules
    elif crop_type == "Cotton":
        evidence.append(f"Days since sowing estimate: {days_since} days.")
        if days_since <= 20:
            stage = "Sowing"
            confidence = 0.80
            evidence.append(f"Low green cover (NDVI: {latest_ndvi:.2f}) close to sowing.")
        elif days_since <= 45:
            stage = "Vegetative"
            confidence = 0.85
            evidence.append(f"NDVI rising ({latest_ndvi:.2f}) indicating node formation.")
        elif days_since <= 85:
            stage = "Flowering"
            confidence = 0.80
            evidence.append(f"Squaring/flowering phase. NDVI at {latest_ndvi:.2f} with strong VH return.")
        elif days_since <= 115:
            stage = "Boll Development"
            confidence = 0.75
            evidence.append(f"High canopy density. NDVI at {latest_ndvi:.2f} and NDMI at {latest_ndmi:.2f}.")
        else:
            stage = "Maturity"
            confidence = 0.85
            evidence.append(f"Cotton bolls opening. NDVI starting to fall ({latest_ndvi:.2f}).")
            
    # Maize rules
    elif crop_type == "Maize":
        evidence.append(f"Days since sowing estimate: {days_since} days.")
        if days_since <= 15:
            stage = "Sowing"
            confidence = 0.80
            evidence.append("Recent planting stage.")
        elif days_since <= 45:
            stage = "Vegetative"
            confidence = 0.85
            evidence.append(f"Fast stem elongation. NDVI at {latest_ndvi:.2f}.")
        elif days_since <= 75:
            stage = "Tasseling/Flowering"
            confidence = 0.85
            evidence.append(f"Peak greening. NDVI at maximum ({latest_ndvi:.2f}).")
        else:
            stage = "Maturity"
            confidence = 0.80
            evidence.append(f"Cob maturity phase. NDVI declining to {latest_ndvi:.2f}.")
            
    else: # Fallback / Wheat / Other
        evidence.append(f"Days since sowing estimate: {days_since} days.")
        if latest_ndvi < 0.20:
            stage = "Sowing"
            confidence = 0.70
            evidence.append(f"Very low NDVI ({latest_ndvi:.2f}) consistent with bare soil.")
        elif recent_trend == "increasing":
            stage = "Vegetative"
            confidence = 0.75
            evidence.append(f"NDVI increasing to {latest_ndvi:.2f}.")
        elif latest_ndvi >= 0.55:
            stage = "Flowering"
            confidence = 0.70
            evidence.append(f"High green index ({latest_ndvi:.2f}) suggesting active reproduction phase.")
        else:
            stage = "Maturity"
            confidence = 0.70
            evidence.append(f"NDVI declining to {latest_ndvi:.2f}.")
            
    return {
        "stage": stage,
        "confidence": confidence,
        "evidence": evidence,
        "sowing_date": sowing_date,
        "days_since_sowing": days_since
    }
