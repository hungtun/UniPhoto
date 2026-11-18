from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.photo import (
    ClusterListResponse,
    DuplicateListResponse,
    OpenMultipleRequest,
)
from app.services import photo_service

router = APIRouter()


@router.get("/{photo_id}/thumbnail", summary="Tạo và trả ảnh thumbnail (.jpg) trực tiếp từ RAM")
def get_photo_thumbnail(
    photo_id: int,
    size: int = Query(default=360, ge=100, le=1600),
    db: Session = Depends(get_db),
):
    try:
        image_bytes = photo_service.generate_thumbnail_bytes(
            db=db, photo_id=photo_id, max_size=size
        )
        return Response(
            content=image_bytes,
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=3600"},
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi tạo thumbnail: {e}",
        )


@router.get("/clusters", response_model=ClusterListResponse, summary="Lấy danh sách các cụm ảnh tương tự AI kèm ảnh đề xuất giữ")
def get_ai_clusters(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return photo_service.list_ai_clusters(db=db, limit=limit, offset=offset)


@router.get("/duplicates", response_model=DuplicateListResponse, summary="Lấy danh sách các nhóm ảnh trùng 100% (ưu tiên giữ file dung lượng lớn nhất)")
def get_duplicate_groups(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return photo_service.list_duplicate_groups(db=db, limit=limit, offset=offset)


@router.post("/rescore", summary="Chấm điểm lại các cụm ảnh tương tự AI và đồng bộ nhóm ảnh trùng theo dung lượng")
def rescore_photos(db: Session = Depends(get_db)):
    try:
        res = photo_service.rescore_all_photos(db=db)
        return {
            "message": f"Đã chấm điểm thẩm mỹ & chất lượng cho {res['scored_count']} ảnh tương tự.",
            **res,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi chấm điểm ảnh: {e}",
        )


@router.post("/{photo_id}/open", summary="Mở ảnh trong Preview hoặc Finder của macOS")
def open_photo_on_mac(
    photo_id: int,
    mode: str = Query(default="preview", pattern="^(preview|finder)$"),
    db: Session = Depends(get_db),
):
    try:
        path = photo_service.open_single_photo(db=db, photo_id=photo_id, mode=mode)
        return {"message": f"Đã mở {path} ({mode})"}
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/open-multiple", summary="Mở cùng lúc cả nhóm ảnh trong Preview")
def open_multiple_photos_on_mac(
    request: OpenMultipleRequest, db: Session = Depends(get_db)
):
    try:
        count = photo_service.open_multiple_photos(db=db, photo_ids=request.photo_ids)
        return {"message": f"Đã mở {count} ảnh trong Preview"}
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/delete-multiple",
    summary="Chuyển hàng loạt ảnh đã chọn vào Thùng rác macOS (Smart Cleanup)",
)
def delete_multiple_photos_by_ids(
    request: OpenMultipleRequest, db: Session = Depends(get_db)
):
    try:
        res = photo_service.remove_multiple_photos(db=db, photo_ids=request.photo_ids)
        return {
            "message": f"Đã chuyển {res['deleted_count']} ảnh vào Thùng rác",
            "deleted_count": res["deleted_count"],
            "freed_bytes": res["freed_bytes"],
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi chuyển hàng loạt ảnh vào Thùng rác: {e}",
        )


@router.delete(
    "/{photo_id}",
    summary="Chuyển ảnh vào Thùng rác macOS và xóa khỏi Database",
)
def delete_photo_by_id(photo_id: int, db: Session = Depends(get_db)):
    try:
        deleted_id = photo_service.remove_photo(db=db, photo_id=photo_id)
        return {"message": "Đã chuyển ảnh vào Thùng rác", "deleted_id": deleted_id}
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi chuyển ảnh vào Thùng rác: {e}",
        )


@router.post("/reset", summary="Xóa sạch toàn bộ Database để quét lại từ đầu")
def reset_database_and_cache(db: Session = Depends(get_db)):
    try:
        photo_service.reset_all_data(db=db)
        return {"message": "Đã làm sạch toàn bộ Database."}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi làm sạch Database: {e}",
        )
