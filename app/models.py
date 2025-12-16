"""Database models for Go-Dhong Garden Manager."""
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Garden(Base):
    """Garden map with customizable grid dimensions."""
    __tablename__ = "gardens"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    rows = Column(Integer, default=4, nullable=False)
    cols = Column(Integer, default=4, nullable=False)
    description = Column(String, nullable=True)
    is_active = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    plants = relationship("Plant", back_populates="garden", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Garden(id={self.id}, name={self.name}, size={self.rows}×{self.cols})>"


class Plant(Base):
    """Individual plant in a garden plot."""
    __tablename__ = "plants"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    garden_id = Column(Integer, ForeignKey("gardens.id"), nullable=True)  # Nullable for migration
    grid_x = Column(Integer, nullable=False)  # Row position
    grid_y = Column(Integer, nullable=False)  # Column position
    status = Column(String, default="healthy", nullable=False)
    planted_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    garden = relationship("Garden", back_populates="plants")
    scans = relationship("LeafLog", back_populates="plant", cascade="all, delete-orphan")
    
    # Unique constraint: one plant per grid position (per garden in future)
    __table_args__ = (
        UniqueConstraint("grid_x", "grid_y", name="unique_grid_position"),
    )
    
    def __repr__(self):
        return f"<Plant(id={self.id}, name={self.name}, pos=({self.grid_x},{self.grid_y}))>"


class LeafLog(Base):
    """Scan log entry with leaf measurements."""
    __tablename__ = "leaf_logs"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=True)
    leaf_area_cm2 = Column(Float, nullable=False)
    coin_detected = Column(Boolean, default=False, nullable=False)
    segmented_image_path = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    plant = relationship("Plant", back_populates="scans")
    
    def __repr__(self):
        return f"<LeafLog(id={self.id}, area={self.leaf_area_cm2}cm², plant_id={self.plant_id})>"
