from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.user import User
from app.services.external_status import check_bhoonidhi_status

router = APIRouter(prefix="/bhoonidhi", tags=["bhoonidhi"])


@router.get("/health")
async def bhoonidhi_health(_: User = Depends(get_current_user)):
    """Run a sanitized Bhoonidhi connectivity diagnostic for an authenticated user."""
    return await check_bhoonidhi_status()
