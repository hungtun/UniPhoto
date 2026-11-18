from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class PhotoItemResponse(BaseModel):
    id: int
    file_name: str
    folder_name: str
    file_path: str
    file_size: int
    width: Optional[int] = None
    height: Optional[int] = None
    timestamp: Optional[datetime] = None
    status: str
    is_best: bool = False
    quality_score: Optional[float] = None
    sharpness_score: Optional[float] = None
    exposure_score: Optional[float] = None
    contrast_score: Optional[float] = None
    aesthetic_score: Optional[float] = None
    composition_score: Optional[float] = None
    face_score: Optional[float] = None
    pose_score: Optional[float] = None
    tilt_angle: Optional[float] = None
    has_closed_eyes: Optional[bool] = None
    aesthetic_tags: List[str] = []
    thumbnail_url: str


class ClusterGroupItem(BaseModel):
    cluster_id: int
    best_photo_id: Optional[int] = None
    photo_count: int
    has_aesthetic_scores: bool = False
    photos: List[PhotoItemResponse]


class ClusterListResponse(BaseModel):
    total_clusters: int
    total_bytes: int = 0
    total_photos: int = 0
    disconnected_volumes: List[str] = []
    items: List[ClusterGroupItem]


class DuplicateGroupItem(BaseModel):
    group_index: int
    phash: str
    best_photo_id: Optional[int] = None
    total_photos: int
    duplicate_count: int
    photos: List[PhotoItemResponse]


class DuplicateListResponse(BaseModel):
    total_groups: int
    total_bytes: int = 0
    total_photos: int = 0
    disconnected_volumes: List[str] = []
    items: List[DuplicateGroupItem]


class OpenMultipleRequest(BaseModel):
    photo_ids: List[int]
