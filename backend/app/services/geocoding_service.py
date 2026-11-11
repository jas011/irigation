import httpx
import logging
from typing import Optional, Dict, Any
from app.schemas.field import LocationResponse

logger = logging.getLogger(__name__)

class GeocodingService:
    NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
    
    @classmethod
    async def reverse_geocode(cls, latitude: float, longitude: float) -> LocationResponse:
        """
        Reverse geocodes coordinate centroid using OpenStreetMap Nominatim.
        Implements error handling and fallback defaults to prevent app failures.
        """
        headers = {
            "User-Agent": "AgriSense-Advisor/1.0 (contact@agrisense.local; support@agrisense.local)"
        }
        params = {
            "lat": latitude,
            "lon": longitude,
            "format": "jsonv2",
            "zoom": 18,
            "addressdetails": 1
        }
        
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.get(cls.NOMINATIM_URL, params=params, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    address = data.get("address", {})
                    
                    # Resilience: Match multiple alternative address fields returned by Nominatim
                    village = (
                        address.get("village") or 
                        address.get("suburb") or 
                        address.get("town") or 
                        address.get("city_district") or 
                        address.get("hamlet") or 
                        address.get("neighbourhood") or
                        address.get("locality")
                    )
                    
                    district = (
                        address.get("county") or 
                        address.get("city") or 
                        address.get("state_district")
                    )
                    
                    state = address.get("state")
                    country = address.get("country")
                    postal_code = address.get("postcode")
                    
                    return LocationResponse(
                        village=village,
                        district=district,
                        state=state,
                        country=country,
                        postal_code=postal_code
                    )
                else:
                    logger.warning(f"Nominatim returned status code {response.status_code}")
        except Exception as e:
            logger.error(f"Reverse geocoding failed: {str(e)}")
            
        # Fallback to empty values if Nominatim is rate-limited or fails
        return LocationResponse()
