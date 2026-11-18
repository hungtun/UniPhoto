from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.scan import ScanRequest, ScanResponse, PhotoItemSummary
from app.services.progress_tracker import get_progress, request_cancel

router = APIRouter()


@router.get("/progress", summary="Lấy tiến độ quét thư mục và gom cụm AI theo thời gian thực")
async def read_scan_progress():
    return get_progress()


@router.post("/cancel", summary="Yêu cầu dừng tác vụ quét / gom cụm / chấm điểm đang chạy")
@router.post("/cancel/", include_in_schema=False)
def cancel_active_task():
    request_cancel()
    return {
        "message": "Đã gửi yêu cầu dừng tác vụ.",
        "cancel_requested": True,
    }


@router.post("", response_model=ScanResponse, summary="Quét thư mục ảnh và phân loại trùng lặp 100%")
@router.post("/", response_model=ScanResponse, include_in_schema=False)
def scan_photos(request: ScanRequest, db: Session = Depends(get_db)):
    """
    Endpoint nhận đường dẫn thư mục tuyệt đối, duyệt toàn bộ ảnh (.jpg, .jpeg, .png, .heic),
    trích xuất EXIF DateTimeOriginal & kích thước gốc, tính pHash và phân loại trùng lặp 100%
    (ưu tiên giữ bản có dung lượng lớn nhất, không tự động chấm điểm).
    """
    try:
        from app.services.scanner import scan_directory

        result = scan_directory(folder_path=request.folder_path, db=db)
        cancelled = bool(result.get("cancelled", False))
        message = (
            "Đã dừng quét thư mục theo yêu cầu."
            if cancelled
            else "Quét thư mục và phân loại trùng lặp hoàn tất."
        )
        return ScanResponse(
            message=message,
            folder_path=result["folder_path"],
            total_found=result["total_found"],
            new_added=result["new_added"],
            exact_duplicates=result["exact_duplicates"],
            already_indexed=result["already_indexed"],
            errors_count=result["errors_count"],
            duration_seconds=result["duration_seconds"],
            cancelled=cancelled,
            items=[
                PhotoItemSummary(
                    id=item.id,
                    file_path=item.file_path,
                    file_size=item.file_size,
                    timestamp=item.timestamp,
                    phash=item.phash,
                    quality_score=None,
                    status=item.status,
                )
                for item in result["items"][:500]
            ],
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi trong quá trình xử lý: {str(e)}",
        )
