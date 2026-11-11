from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, index=True)
    field_id = Column(String, ForeignKey("fields.field_id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Range of analysis
    start_date = Column(String, nullable=False)
    end_date = Column(String, nullable=False)
    
    # Stage 2 Outputs
    crop = Column(String, nullable=True)
    crop_confidence = Column(Float, nullable=True)
    growth_stage = Column(String, nullable=True)
    growth_stage_confidence = Column(Float, nullable=True)
    sowing_date = Column(String, nullable=True)
    days_since_sowing = Column(Integer, nullable=True)
    
    # Stage 3 Outputs
    stress_score = Column(Float, nullable=True)
    stress_class = Column(String, nullable=True)
    
    # Quality and Versioning
    data_quality = Column(String, nullable=False, default="Good")
    model_version = Column(String, nullable=False, default="1.0.0")
    
    # Heavy Payload caching (stored as JSON)
    classification_map = Column(JSON, nullable=True)
    stress_map = Column(JSON, nullable=True)
    time_series = Column(JSON, nullable=True)
    stress_time_series = Column(JSON, nullable=True)
    
    # Timestamp of when the run occurred
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    field = relationship("Field", back_populates="analyses")
