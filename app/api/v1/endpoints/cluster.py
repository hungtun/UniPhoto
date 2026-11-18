from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.cluster import (
    AestheticScoreResponse,
    ClusterRequest,
    ClusterResponse,
)

router = APIRouter()


@router.post("", response_model=ClusterResponse, summary="Gom cụm ảnh tương đồng bằng AI (MobileNetV2)")
@router.post("/", response_model=ClusterResponse, include_in_schema=False)
def cluster_photos(request: ClusterRequest = ClusterRequest(), db: Session = Depends(get_db)):
    """
    Trích xuất vector đặc trưng bằng MobileNetV2 theo từng lô (Batch Processing),
    gom cụm các ảnh tương đồng thị giác và khởi tạo bản đề xuất giữ theo dung lượng lớn nhất
    (không tự động chấm điểm cho đến khi người dùng yêu cầu).
    """
    try:
        from app.services.ai_engine import cluster_unassigned_photos

        result = cluster_unassigned_photos(
            db=db,
            batch_size=request.batch_size,
            similarity_threshold=request.similarity_threshold,
        )
        cancelled = bool(result.get("cancelled", False))
        message = (
            "Đã dừng gom cụm AI theo yêu cầu."
            if cancelled
            else "Gom cụm ảnh bằng AI hoàn tất."
        )
        return ClusterResponse(
            message=message,
            total_processed=result["total_processed"],
            clusters_created=result["clusters_created"],
            photos_clustered=result["photos_clustered"],
            duration_seconds=result["duration_seconds"],
            cancelled=cancelled,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi trong quá trình gom cụm ảnh: {str(e)}",
        )


@router.post(
    "/aesthetic-score",
    response_model=AestheticScoreResponse,
    summary="Chấm điểm thẩm mỹ & chất lượng (khuôn mặt, mắt nhắm, bố cục & góc máy) cho cụm ảnh tương tự AI",
)
@router.post("/aesthetic-score/", response_model=AestheticScoreResponse, include_in_schema=False)
def score_ai_clusters_aesthetics(db: Session = Depends(get_db)):
    """
    Chấm điểm theo yêu cầu (On-Demand) cho các cụm ảnh tương đồng AI (chất lượng kỹ thuật, độ nét khuôn mặt,
    mắt nhắm và bố cục/độ nghiêng góc máy), không áp dụng cho nhóm ảnh trùng lặp 100%.
    """
    try:
        from app.services.aesthetic_scorer import score_clusters_aesthetics

        result = score_clusters_aesthetics(db=db)
        cancelled = bool(result.get("cancelled", False))
        message = (
            "Đã dừng chấm điểm thẩm mỹ AI theo yêu cầu."
            if cancelled
            else "Hoàn tất chấm điểm thẩm mỹ AI."
        )
        return AestheticScoreResponse(
            message=message,
            clusters_scored=result["clusters_scored"],
            photos_scored=result["photos_scored"],
            best_changed_count=result["best_changed_count"],
            duration_seconds=result["duration_seconds"],
            cancelled=cancelled,
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi trong quá trình chấm điểm thẩm mỹ AI: {str(e)}",
        )
