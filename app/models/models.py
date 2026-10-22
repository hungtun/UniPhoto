from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


class Photo(Base):
    __tablename__ = "photos"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    # MySQL yêu cầu VARCHAR có độ dài xác định khi đánh index/unique
    file_path = Column(String(500), unique=True, index=True, nullable=False)
    file_size = Column(Integer, nullable=False)
    timestamp = Column(DateTime, nullable=True, index=True)
    phash = Column(String(64), index=True, nullable=True)
    quality_score = Column(Float, nullable=True)
    cluster_id = Column(Integer, ForeignKey("clusters.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(50), default="keep", nullable=False, index=True)  # "keep", "delete", "exact_duplicate"

    # Quan hệ với Cluster
    cluster = relationship("Cluster", foreign_keys=[cluster_id], back_populates="photos")


class Cluster(Base):
    __tablename__ = "clusters"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    # use_alter=True giúp xử lý quan hệ vòng tròn (circular foreign key) an toàn trong MySQL DDL
    best_photo_id = Column(
        Integer,
        ForeignKey("photos.id", ondelete="SET NULL", use_alter=True, name="fk_cluster_best_photo"),
        nullable=True,
    )

    # Quan hệ danh sách các ảnh trong cluster
    photos = relationship("Photo", foreign_keys="Photo.cluster_id", back_populates="cluster")
    best_photo = relationship("Photo", foreign_keys=[best_photo_id])
