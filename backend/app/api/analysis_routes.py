from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.field import Field
from app.models.user import User
from app.services.analysis.crop_analysis_service import CropAnalysisService
from app.services.analysis.moisture_analysis_service import MoistureAnalysisService
from app.services.season_service import SeasonService

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/current-season")
async def get_current_season(date: str | None = None):
    """
    Returns the current Indian agricultural cropping season determined via OpenAI.
    """
    return await SeasonService.get_current_season(for_date=date)



@router.post("/crop")
async def analyze_crop(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    field_id = payload.get("field_id")
    geometry = payload.get("geometry")
    if not field_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="field_id is required.")
    if not geometry:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="AOI geometry is required.")

    field = db.query(Field).filter(Field.field_id == field_id).first()
    if not field:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Field with ID {field_id} not found.")
    if field.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to analyze this field.")

    try:
        return await CropAnalysisService.analyze_field(
            geometry=geometry,
            start_date=payload.get("start_date"),
            end_date=payload.get("end_date"),
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/moisture")
async def analyze_moisture(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    field_id = payload.get("field_id")
    geometry = payload.get("geometry")
    crop_prediction = payload.get("crop_prediction")
    growth_stage = payload.get("growth_stage")

    if not field_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="field_id is required.")
    if not geometry:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="AOI geometry is required.")
    if not crop_prediction:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="crop_prediction is required.")

    field = db.query(Field).filter(Field.field_id == field_id).first()
    if not field:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Field with ID {field_id} not found.")
    if field.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to analyze this field.")

    try:
        return await MoistureAnalysisService.analyze_field(
            geometry=geometry,
            crop_prediction=crop_prediction,
            growth_stage=growth_stage or "unknown",
            start_date=payload.get("start_date"),
            end_date=payload.get("end_date"),
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
