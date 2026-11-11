from geoalchemy2.shape import to_shape
from geoalchemy2.elements import WKBElement
from shapely.geometry import box, mapping, shape, Point
from typing import Dict, Any

def wkb_to_geojson(wkb_element: WKBElement) -> Dict[str, Any]:
    """
    Converts a GeoAlchemy WKBElement into a GeoJSON geometry dictionary.
    """
    if wkb_element is None:
        return {}
    shapely_geom = to_shape(wkb_element)
    return mapping(shapely_geom)

def geojson_to_shapely(geojson_dict: Dict[str, Any]):
    """
    Converts a GeoJSON geometry dictionary into a Shapely geometry object.
    """
    return shape(geojson_dict)


def clipped_sample_cell(coordinates, geometry_geojson: Dict[str, Any], cell_size: float = 0.00009):
    """Return a small sample cell clipped to the exact selected AOI.

    Earth Engine returns representative pixel points. Converting each point to
    a 10 m-sized cell gives the UI a real spatial subregion, while intersecting
    it with the original polygon guarantees that no result leaves the AOI.
    """
    try:
        aoi = shape(geometry_geojson)
        lon, lat = float(coordinates[0]), float(coordinates[1])
        half = cell_size / 2
        cell = box(lon - half, lat - half, lon + half, lat + half).intersection(aoi)
        if cell.is_empty:
            return None
        return mapping(cell)
    except (TypeError, ValueError, IndexError):
        return None
