from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoalchemy2 import Geometry
from app.core.database import Base

class Field(Base):
    __tablename__ = "fields"

    id = Column(Integer, primary_key=True, index=True)
    field_id = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    analyses = relationship("AnalysisResult", back_populates="field", cascade="all, delete-orphan")
    
    # PostGIS Spatial Fields
    geometry = Column(Geometry(geometry_type="POLYGON", srid=4326, spatial_index=True), nullable=False)
    centroid = Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    
    # Area and Perimeter Measurements
    area_m2 = Column(Float, nullable=False)
    area_hectares = Column(Float, nullable=False)
    area_acres = Column(Float, nullable=False)
    perimeter_m = Column(Float, nullable=False)
    
    # Centroid coordinate extraction for convenience
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    
    # Location Metadata (Reverse Geocoded)
    village = Column(String, nullable=True)
    district = Column(String, nullable=True)
    state = Column(String, nullable=True)
    country = Column(String, nullable=True)
    postal_code = Column(String, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", backref="fields")
