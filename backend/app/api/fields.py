from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
import logging
import re
from datetime import datetime
from typing import List
from geoalchemy2.elements import WKTElement

from app.core.database import get_db
from app.models.field import Field
from app.models.analysis import AnalysisResult
from app.models.user import User
from app.schemas.field import (
    FieldValidationRequest, 
    FieldValidationResponse, 
    FieldCreateRequest, 
    FieldResponse,
    LocationResponse,
    FieldAIVerificationRequest,
    FieldAIVerificationResponse
)
from app.services.field_validation_service import FieldValidationService
from app.services.field_ai_verification_service import FieldAIVerificationService
from app.services.geocoding_service import GeocodingService
from app.api.deps import get_current_user
from app.utils.geometry import wkb_to_geojson


router = APIRouter(prefix="/fields", tags=["fields"])
logger = logging.getLogger(__name__)
FIELD_ID_PATTERN = re.compile(r"^FLD-(\d{4})-(\d{6})$")


def generate_next_field_id(db: Session, year: int | None = None) -> str:
    """Allocate the next sequential field id for the given year.

    Uses the highest existing numeric suffix, not a row count, so deleted
    records cannot cause duplicate-key collisions.
    """
    current_year = year or datetime.now().year
    year_prefix = f"FLD-{current_year}-"
    existing_ids = (
        db.query(Field.field_id)
        .filter(Field.field_id.like(f"{year_prefix}%"))
        .all()
    )

    max_suffix = 0
    for (field_id,) in existing_ids:
        match = FIELD_ID_PATTERN.match(field_id or "")
        if not match or int(match.group(1)) != current_year:
            continue
        max_suffix = max(max_suffix, int(match.group(2)))

    return f"{year_prefix}{max_suffix + 1:06d}"

@router.post("/validate", response_model=FieldValidationResponse)
async def validate_field(
    req: FieldValidationRequest, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # Protected route
):
    """
    Validates a drawn field polygon. Centroid coordinate calculations and reverse geocoding
    are performed without saving the field.
    """
    validation_res = FieldValidationService.validate_field(db, req.geometry)
    
    if validation_res.valid:
        # Perform reverse geocoding on the centroid coordinate
        location_data = await GeocodingService.reverse_geocode(
            validation_res.centroid.latitude, 
            validation_res.centroid.longitude
        )
        validation_res.location = location_data
        
    return validation_res

@router.post("/verify-ai", response_model=FieldAIVerificationResponse)
async def verify_field_ai(
    req: FieldAIVerificationRequest,
    current_user: User = Depends(get_current_user)  # Protected route
):
    """
    Validates whether the selected region appears to be an actual agricultural/farmland field
    using OpenAI Vision analysis on satellite imagery before proceeding to Phase 2.
    """
    return await FieldAIVerificationService.verify_field(req.geometry, req.image_base64)

@router.post("", response_model=FieldResponse, status_code=status.HTTP_201_CREATED)

async def create_field(
    req: FieldCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Performs authoritative validation, generates a unique Field ID (FLD-YYYY-000XXX),
    and stores the field boundary polygon inside PostGIS database, linked to the authenticated user.
    """
    # 1. Authoritative Validation
    validation_res = FieldValidationService.validate_field(db, req.geometry)
    if not validation_res.valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation_res.message
        )
        
    # 2. Reverse Geocode address if not provided in the request
    location_details = req.location
    if not location_details or not location_details.country:
        location_details = await GeocodingService.reverse_geocode(
            validation_res.centroid.latitude, 
            validation_res.centroid.longitude
        )
        
    # 3. Generate sequential unique field id: FLD-YYYY-XXXXXX
    wkt_polygon = _geometry_to_wkt(req.geometry)
    wkt_centroid = f"POINT({validation_res.centroid.longitude} {validation_res.centroid.latitude})"

    db_field = None
    for attempt in range(5):
        field_id = generate_next_field_id(db)
        db_field = Field(
            field_id=field_id,
            user_id=current_user.id,
            geometry=WKTElement(wkt_polygon, srid=4326),
            centroid=WKTElement(wkt_centroid, srid=4326),
            area_m2=validation_res.area_m2,
            area_hectares=validation_res.area_hectares,
            area_acres=validation_res.area_acres,
            perimeter_m=validation_res.perimeter_m,
            latitude=validation_res.centroid.latitude,
            longitude=validation_res.centroid.longitude,
            village=location_details.village,
            district=location_details.district,
            state=location_details.state,
            country=location_details.country,
            postal_code=location_details.postal_code,
        )

        try:
            db.add(db_field)
            db.commit()
            db.refresh(db_field)
            break
        except IntegrityError as exc:
            db.rollback()
            if attempt == 4:
                logger.exception("Failed to allocate a unique field id after retries")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to register field in database: unable to allocate a unique field id.",
                ) from exc
            logger.warning("Field id collision on %s; retrying allocation.", field_id)
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to register field in database: {str(e)}",
            ) from e
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register field in database: unable to allocate a unique field id.",
        )

    return format_field_db_to_response(db_field)


def _geometry_to_wkt(geometry) -> str:
    outer_ring = geometry.coordinates[0]
    wkt_coords = ", ".join([f"{pt[0]} {pt[1]}" for pt in outer_ring])
    return f"POLYGON(({wkt_coords}))"

@router.get("", response_model=List[FieldResponse])
def list_fields(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists all fields registered by the currently authenticated user.
    """
    fields = db.query(Field).filter(Field.user_id == current_user.id).order_by(Field.created_at.desc()).all()
    return [format_field_db_to_response(f) for f in fields]

@router.get("/{field_id}", response_model=FieldResponse)
def get_field(
    field_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves details of a specific field, verifying ownership.
    """
    field = db.query(Field).filter(Field.field_id == field_id).first()
    if not field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Field with ID {field_id} not found."
        )
        
    if field.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this field."
        )
        
    return format_field_db_to_response(field)

@router.put("/{field_id}", response_model=FieldResponse)
def update_field(
    field_id: str,
    req: LocationResponse,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Updates the address or location metadata of a registered field.
    """
    field = db.query(Field).filter(Field.field_id == field_id).first()
    if not field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Field with ID {field_id} not found."
        )
        
    if field.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this field."
        )
        
    # Update text fields
    if req.village is not None:
        field.village = req.village
    if req.district is not None:
        field.district = req.district
    if req.state is not None:
        field.state = req.state
    if req.country is not None:
        field.country = req.country
    if req.postal_code is not None:
        field.postal_code = req.postal_code
        
    db.commit()
    db.refresh(field)
    return format_field_db_to_response(field)

@router.delete("/{field_id}", status_code=status.HTTP_200_OK)
def delete_field(
    field_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Deletes a registered field, verifying ownership.
    """
    field = db.query(Field).filter(Field.field_id == field_id).first()
    if not field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Field with ID {field_id} not found."
        )
        
    if field.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this field."
        )

    try:
        # Delete cached analysis payloads explicitly first. This supports both
        # current databases (which have ON DELETE CASCADE) and older local
        # databases created before that foreign-key rule existed. A bulk query
        # avoids loading potentially large map/time-series JSON into memory.
        deleted_analyses = (
            db.query(AnalysisResult)
            .filter(AnalysisResult.field_id == field_id)
            .delete(synchronize_session=False)
        )
        db.delete(field)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Failed to delete field %s for user %s", field_id, current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to delete the field history. No records were removed; please retry.",
        )

    return {
        "message": f"Field {field_id} deleted successfully.",
        "deleted_analysis_count": deleted_analyses,
    }


def format_field_db_to_response(field: Field) -> FieldResponse:
    """
    Helper utility converting a database Field object to a clean JSON API schema.
    """
    return FieldResponse(
        id=field.id,
        field_id=field.field_id,
        user_id=field.user_id,
        area_m2=field.area_m2,
        area_hectares=field.area_hectares,
        area_acres=field.area_acres,
        perimeter_m=field.perimeter_m,
        latitude=field.latitude,
        longitude=field.longitude,
        village=field.village,
        district=field.district,
        state=field.state,
        country=field.country,
        postal_code=field.postal_code,
        geometry=wkb_to_geojson(field.geometry),
        created_at=field.created_at,
        updated_at=field.updated_at
    )
