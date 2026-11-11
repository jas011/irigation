import ee
from typing import Dict, Any
from app.services.gee.gee_service import gee_get_info, is_gee_ready

def get_crop_and_land_cover_probabilities(geometry_geojson: Dict[str, Any], start_date: str, end_date: str) -> Dict[str, float]:
    """
    Queries GOOGLE/DYNAMICWORLD/V1 to retrieve the land cover class distribution
    for the selected field.
    Dynamic World contains probabilities for 9 classes:
    water, trees, grass, flooded_vegetation, crops, shrub_and_scrub, built, bare, snow_and_ice
    """
    if not is_gee_ready():
        return {}
        
    geom = ee.Geometry(geometry_geojson)
    
    # Load Dynamic World collection
    dw_col = (
        ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
        .filterBounds(geom)
        .filterDate(start_date, end_date)
    )
    
    count = int(gee_get_info(dw_col.size()))
    if count == 0:
        # Try a wider historical filter as a fallback if no recent image
        dw_col = (
            ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
            .filterBounds(geom)
            .limit(10)
        )
        if int(gee_get_info(dw_col.size())) == 0:
            return {}
            
    # Calculate the mean probability image over the time range
    mean_dw = dw_col.select([
        'water', 'trees', 'grass', 'flooded_vegetation', 
        'crops', 'shrub_and_scrub', 'built', 'bare', 'snow_and_ice'
    ]).mean()
    
    # Reduce over the geometry
    stats = gee_get_info(mean_dw.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geom,
        scale=10,
        maxPixels=1e9
    ))
    
    # Normalize probabilities to sum to 1.0 (just in case)
    if not stats:
        return {}
        
    total = sum(v for v in stats.values() if v is not None)
    if total == 0:
        return {}
        
    return {k: (v / total if v is not None else 0.0) for k, v in stats.items()}
