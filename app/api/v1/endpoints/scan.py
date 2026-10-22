from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.scan import ScanRequest, ScanResponse, PhotoItemSummary
from app.services.scanner import scan_directory

router = APIRouter()


@router.post("", response_model=ScanResponse, summary="Quét thư mục ảnh và phân loại trùng lặp")
@router.post("/", response_model=ScanResponse, include_in_schema=False)
def scan_photos(request: ScanRequest, db: Session = Depends(get_db)):
    """
    Endpoint nhận đường dẫn thư mục tuyệt đối, duyệt toàn bộ ảnh (.jpg, .jpeg, .png),
    trích xuất EXIF DateTimeOriginal, tính pHash và phân loại trùng lặp 100%.
    """
    try:
        result = scan_directory(folder_path=request.folder_path, db=db)
        return ScanResponse(
            message="Quét thư mục và phân loại hoàn tất.",
            folder_path=result["folder_path"],
            total_found=result["total_found"],
            new_added=result["new_added"],
            exact_duplicates=result["exact_duplicates"],
            already_indexed=result["already_indexed"],
            errors_count=result["errors_count"],
            duration_seconds=result["duration_seconds"],
            items=[
                PhotoItemSummary(
                    id=item.id,
                    file_path=item.file_path,
                    file_size=item.file_size,
                    timestamp=item.timestamp,
                    phash=item.phash,
                    status=item.status,
                )
                for item in result["items"]
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
