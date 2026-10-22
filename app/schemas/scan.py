from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    folder_path: str = Field(
        ...,
        description="Đường dẫn thư mục tuyệt đối cần quét ảnh (ví dụ: /Users/hung/Pictures hoặc C:/Users/Hung/Pictures/DuLich)",
        examples=["/Users/hung/Pictures/DuLich"],
    )


class PhotoItemSummary(BaseModel):
    id: int
    file_path: str
    file_size: int
    timestamp: Optional[datetime] = None
    phash: Optional[str] = None
    status: str

    class Config:
        from_attributes = True


class ScanResponse(BaseModel):
    message: str
    folder_path: str
    total_found: int
    new_added: int
    exact_duplicates: int
    already_indexed: int
    errors_count: int
    duration_seconds: float
    items: List[PhotoItemSummary] = []
