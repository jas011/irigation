import ee
from typing import Dict, Any
from app.services.gee.gee_service import gee_get_info, is_gee_ready

def get_water_occurrence(geometry_geojson: Dict[str, Any]) -> float:
    """
    Queries JRC/GSW1_4/GlobalSurfaceWater to check if there is permanent
    surface water within the field boundary.
    Returns the average water occurrence percentage (0.0 to 100.0) in the AOI.
    """
    if not is_gee_ready():
        return 0.0
        
    geom = ee.Geometry(geometry_geojson)
    
    # Load JRC Global Surface Water dataset (static metadata containing historical occurrence)
    jrc_water = ee.Image("JRC/GSW1_4/GlobalSurfaceWater")
    
    # Select the 'occurrence' band (percentage of times water was present historically)
    occurrence = jrc_water.select('occurrence')
    
    # Reduce over the geometry to get the mean occurrence
    stats = gee_get_info(occurrence.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geom,
        scale=30, # JRC resolution is 30m
        maxPixels=1e9
    ))
    
    if not stats or stats.get('occurrence') is None:
        return 0.0
        
    return float(stats.get('occurrence'))
