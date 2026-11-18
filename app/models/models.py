from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


class Photo(Base):
    __tablename__ = "photos"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    file_path = Column(String(500), unique=True, index=True, nullable=False)
    file_size = Column(Integer, nullable=False)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    timestamp = Column(DateTime, nullable=True, index=True)
    phash = Column(String(64), index=True, nullable=True)
    quality_score = Column(Float, nullable=True)
    sharpness_score = Column(Float, nullable=True)
    exposure_score = Column(Float, nullable=True)
    contrast_score = Column(Float, nullable=True)
    aesthetic_score = Column(Float, nullable=True)
    composition_score = Column(Float, nullable=True)
    face_score = Column(Float, nullable=True)
    pose_score = Column(Float, nullable=True)
    tilt_angle = Column(Float, nullable=True)
    has_closed_eyes = Column(Boolean, nullable=True)
    aesthetic_tags = Column(String(500), nullable=True)
    cluster_id = Column(Integer, ForeignKey("clusters.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(50), default="keep", nullable=False, index=True)  # "keep", "delete", "exact_duplicate"

    # Quan hệ với Cluster
    cluster = relationship("Cluster", foreign_keys=[cluster_id], back_populates="photos")


class Cluster(Base):
    __tablename__ = "clusters"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    best_photo_id = Column(
        Integer,
        ForeignKey("photos.id", ondelete="SET NULL", use_alter=True, name="fk_cluster_best_photo"),
        nullable=True,
    )

    # Quan hệ danh sách các ảnh trong cluster
    photos = relationship("Photo", foreign_keys="Photo.cluster_id", back_populates="cluster")
    best_photo = relationship("Photo", foreign_keys=[best_photo_id])
