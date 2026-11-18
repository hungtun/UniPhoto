from pydantic import BaseModel, Field


class ClusterRequest(BaseModel):
    batch_size: int = Field(
        default=16,
        ge=1,
        le=128,
        description="Số lượng ảnh xử lý trong mỗi lô (batch) để tối ưu RAM",
        examples=[16],
    )
    similarity_threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Ngưỡng độ tương đồng Cosine (0.0 - 1.0) để gom chung một cụm",
        examples=[0.85],
    )


class ClusterResponse(BaseModel):
    message: str
    total_processed: int
    clusters_created: int
    photos_clustered: int
    duration_seconds: float
    cancelled: bool = False


class AestheticScoreResponse(BaseModel):
    message: str
    clusters_scored: int
    photos_scored: int
    best_changed_count: int
    duration_seconds: float
    cancelled: bool = False
