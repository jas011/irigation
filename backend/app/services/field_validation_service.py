import logging
import math
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.validation import explain_validity
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.schemas.field import GeoJSONPolygon, CentroidResponse, LocationResponse, FieldValidationResponse
from app.services.geocoding_service import GeocodingService

logger = logging.getLogger(__name__)

# Constants for agricultural field limits
MIN_FIELD_AREA_M2 = 100.0        # 0.01 hectares (approx 0.025 acres)
MAX_FIELD_AREA_M2 = 10000000.0   # 1000 hectares (approx 2471 acres)

class FieldValidationService:
    @staticmethod
    def check_coordinates_format(coordinates: list) -> tuple[bool, str]:
        """
        Check that coordinates list is a valid nested structure for a Polygon.
        """
        if not coordinates or not isinstance(coordinates, list):
            return False, "Coordinates must be a list."
        if len(coordinates) == 0:
            return False, "Polygon coordinates list is empty."
        
        outer_ring = coordinates[0]
        if not isinstance(outer_ring, list) or len(outer_ring) < 4:
            return False, "Polygon outer ring must contain at least 4 coordinates (3 vertices + 1 closing point)."
            
        for idx, pt in enumerate(outer_ring):
            if not isinstance(pt, list) or len(pt) < 2:
                return False, f"Coordinate point at index {idx} is invalid (must be a [lng, lat] list)."
            lng, lat = pt[0], pt[1]
            if not (-180.0 <= lng <= 180.0) or not (-90.0 <= lat <= 90.0):
                return False, f"Coordinates at index {idx} ({lng}, {lat}) out of range (longitude: -180 to 180, latitude: -90 to 90)."
                
        # Check if polygon is closed
        if outer_ring[0] != outer_ring[-1]:
            return False, "Polygon outer ring must be closed (first and last coordinates must be identical)."
            
        return True, ""

    @classmethod
    def validate_field(cls, db: Session, geometry: GeoJSONPolygon) -> FieldValidationResponse:
        """
        Validates the polygon geometry locally using Shapely and authoritatively using PostGIS.
        Calculates area, perimeter, and centroid.
        """
        coords = geometry.coordinates
        
        # 1. Format and coordinate range check
        fmt_ok, fmt_err = cls.check_coordinates_format(coords)
        if not fmt_ok:
            return cls._invalid_response(geometry, fmt_err)
            
        # 2. Local Shapely check
        try:
            # Coordinates are [lng, lat], Shapely can handle this
            outer_ring = coords[0]
            # Convert list of lists to tuple list for Shapely
            shapely_coords = [(pt[0], pt[1]) for pt in outer_ring]
            shapely_poly = ShapelyPolygon(shapely_coords)
            
            if not shapely_poly.is_valid:
                validity_reason = explain_validity(shapely_poly)
                return cls._invalid_response(
                    geometry, 
                    f"Boundary is self-intersecting or invalid. Reason: {validity_reason}."
                )
        except Exception as e:
            logger.error(f"Shapely validation error: {str(e)}")
            return cls._invalid_response(geometry, f"Malformed polygon geometry: {str(e)}")

        # 3. Authoritative PostGIS check and calculations
        # Convert coords to WKT (Well-Known Text) for PostGIS
        # WKT format: POLYGON((lng1 lat1, lng2 lat2, ...))
        wkt_coords = ", ".join([f"{pt[0]} {pt[1]}" for pt in outer_ring])
        wkt_str = f"POLYGON(({wkt_coords}))"
        
        try:
            # Query PostGIS for spatial validation and geography-based calculations
            query = text("""
                SELECT 
                    ST_IsValid(ST_GeomFromText(:wkt, 4326)) as is_valid,
                    ST_Area(ST_GeomFromText(:wkt, 4326)::geography) as area_m2,
                    ST_Perimeter(ST_GeomFromText(:wkt, 4326)::geography) as perimeter_m,
                    ST_X(ST_Centroid(ST_GeomFromText(:wkt, 4326))) as centroid_lng,
                    ST_Y(ST_Centroid(ST_GeomFromText(:wkt, 4326))) as centroid_lat
            """)
            
            spatial_data = db.execute(query, {"wkt": wkt_str}).fetchone()
            
            if spatial_data and spatial_data.is_valid:
                area_m2 = float(spatial_data.area_m2)
                perimeter_m = float(spatial_data.perimeter_m)
                centroid_lng = float(spatial_data.centroid_lng)
                centroid_lat = float(spatial_data.centroid_lat)
            else:
                raise ValueError("PostGIS returned invalid result")
        except Exception as e:
            logger.warning(f"PostGIS spatial query fallback to Shapely: {str(e)}")
            # Geodesic approximation using Shapely
            centroid = shapely_poly.centroid
            centroid_lng, centroid_lat = float(centroid.x), float(centroid.y)
            lat_rad = math.radians(centroid_lat)
            m_per_deg_lat = 111132.954 - 559.822 * math.cos(2 * lat_rad) + 1.175 * math.cos(4 * lat_rad)
            m_per_deg_lon = 111412.84 * math.cos(lat_rad) - 93.5 * math.cos(3 * lat_rad)
            
            # Approximate area
            area_m2 = shapely_poly.area * m_per_deg_lat * m_per_deg_lon
            perimeter_m = shapely_poly.length * ((m_per_deg_lat + m_per_deg_lon) / 2.0)

        # Area limit validation
        if area_m2 < MIN_FIELD_AREA_M2:
            return cls._invalid_response(
                geometry, 
                f"Field is too small ({area_m2:.1f} m²). Minimum required agricultural area is {MIN_FIELD_AREA_M2} m²."
            )
        if area_m2 > MAX_FIELD_AREA_M2:
            return cls._invalid_response(
                geometry, 
                f"Field is too large ({area_m2/10000:.1f} hectares). Maximum allowed area is {MAX_FIELD_AREA_M2/10000:.1f} hectares."
            )
            
        # Convert units
        area_hectares = area_m2 / 10000.0
        area_acres = area_m2 / 4046.8564224
        
        return FieldValidationResponse(
            valid=True,
            geometry_valid=True,
            area_valid=True,
            area_m2=round(area_m2, 2),
            area_hectares=round(area_hectares, 3),
            area_acres=round(area_acres, 3),
            perimeter_m=round(perimeter_m, 2),
            centroid=CentroidResponse(latitude=round(centroid_lat, 6), longitude=round(centroid_lng, 6)),
            location=LocationResponse(),
            geometry=geometry,
            message="Field boundary successfully validated and ready for analysis."
        )


    @staticmethod
    def _invalid_response(geometry: GeoJSONPolygon, message: str) -> FieldValidationResponse:
        return FieldValidationResponse(
            valid=False,
            geometry_valid=False,
            area_valid=False,
            area_m2=0.0,
            area_hectares=0.0,
            area_acres=0.0,
            perimeter_m=0.0,
            centroid=CentroidResponse(latitude=0.0, longitude=0.0),
            location=LocationResponse(),
            geometry=geometry,
            message=message
        )
