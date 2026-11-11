import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.analysis_routes import router as analysis_router
from app.api.auth import router as auth_router
from app.api.bhoonidhi import router as bhoonidhi_router
from app.api.crop import router as crop_router
from app.api.fields import router as fields_router
from app.api.moisture import router as moisture_router
from app.api.weather import router as weather_router
from app.core.config import settings
from app.core.database import Base, engine
from app.services.external_status import run_startup_checks

logger = logging.getLogger("agrisense.main")


def init_db() -> None:
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
            conn.commit()
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully.")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Database initialization failed: %s", exc)


init_db()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="AgriSense AI Irrigation Advisor backend with AOI-driven crop and moisture analysis.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(fields_router, prefix=settings.API_V1_STR)
app.include_router(analysis_router, prefix=settings.API_V1_STR)
app.include_router(crop_router, prefix=settings.API_V1_STR)
app.include_router(moisture_router, prefix=settings.API_V1_STR)
app.include_router(bhoonidhi_router, prefix=settings.API_V1_STR)
app.include_router(weather_router, prefix=settings.API_V1_STR)


@app.on_event("startup")
async def startup_event() -> None:
    try:
        await run_startup_checks()
    except Exception as exc:  # noqa: BLE001
        logger.exception("External service startup checks failed: %s", exc)


@app.get("/")
def read_root():
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "phase": "stage-2-3-redevelopment",
        "docs": "/docs",
    }
