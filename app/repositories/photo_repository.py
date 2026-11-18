from typing import List, Optional, Tuple
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import Photo


def _apply_excluded_prefixes(query, excluded_prefixes: Optional[List[str]]):
    if excluded_prefixes:
        for prefix in excluded_prefixes:
            if prefix:
                query = query.filter(~Photo.file_path.startswith(prefix, autoescape=True))
    return query


class PhotoRepository:
    @staticmethod
    def get_by_id(db: Session, photo_id: int) -> Optional[Photo]:
        return db.query(Photo).filter(Photo.id == photo_id).first()

    @staticmethod
    def get_by_ids(db: Session, photo_ids: List[int]) -> List[Photo]:
        if not photo_ids:
            return []
        return db.query(Photo).filter(Photo.id.in_(photo_ids)).all()

    @staticmethod
    def get_multi_photo_clusters_page(
        db: Session,
        limit: int,
        offset: int,
        excluded_prefixes: Optional[List[str]] = None,
    ) -> Tuple[int, int, int, List[int]]:
        base_q = _apply_excluded_prefixes(
            db.query(Photo).filter(Photo.cluster_id.isnot(None)),
            excluded_prefixes,
        )
        grouped = (
            base_q.with_entities(
                Photo.cluster_id.label("cluster_id"),
                func.count(Photo.id).label("photo_count"),
                func.coalesce(func.sum(Photo.file_size), 0).label("group_bytes"),
            )
            .group_by(Photo.cluster_id)
            .having(func.count(Photo.id) >= 2)
            .subquery()
        )
        agg_row = db.query(
            func.count(grouped.c.cluster_id),
            func.coalesce(func.sum(grouped.c.group_bytes), 0),
            func.coalesce(func.sum(grouped.c.photo_count), 0),
        ).one()
        total_clusters = int(agg_row[0] or 0)
        total_bytes = int(agg_row[1] or 0)
        total_photos = int(agg_row[2] or 0)
        if total_clusters == 0:
            return 0, 0, 0, []

        cluster_ids = [
            cid
            for (cid,) in db.query(grouped.c.cluster_id)
            .order_by(grouped.c.cluster_id.asc())
            .offset(offset)
            .limit(limit)
            .all()
        ]
        return total_clusters, total_bytes, total_photos, cluster_ids

    @staticmethod
    def get_multi_photo_cluster_ids(
        db: Session,
        limit: int,
        offset: int,
        excluded_prefixes: Optional[List[str]] = None,
    ) -> Tuple[int, List[int]]:
        total, _, _, cluster_ids = PhotoRepository.get_multi_photo_clusters_page(
            db, limit=limit, offset=offset, excluded_prefixes=excluded_prefixes
        )
        return total, cluster_ids

    @staticmethod
    def get_photos_by_cluster(db: Session, cluster_id: int) -> List[Photo]:
        return (
            db.query(Photo)
            .filter(Photo.cluster_id == cluster_id)
            .order_by(Photo.timestamp.asc())
            .all()
        )

    @staticmethod
    def get_photos_by_clusters(db: Session, cluster_ids: List[int]) -> List[Photo]:
        if not cluster_ids:
            return []
        return (
            db.query(Photo)
            .filter(Photo.cluster_id.in_(cluster_ids))
            .order_by(Photo.timestamp.asc())
            .all()
        )

    @staticmethod
    def get_duplicate_groups_page(
        db: Session,
        limit: int,
        offset: int,
        excluded_prefixes: Optional[List[str]] = None,
    ) -> Tuple[int, int, int, List[str]]:
        base_q = _apply_excluded_prefixes(
            db.query(Photo).filter(Photo.phash.isnot(None)),
            excluded_prefixes,
        )
        grouped = (
            base_q.with_entities(
                Photo.phash.label("phash"),
                func.count(Photo.id).label("photo_count"),
                func.coalesce(func.sum(Photo.file_size), 0).label("group_bytes"),
            )
            .group_by(Photo.phash)
            .having(func.count(Photo.id) > 1)
            .subquery()
        )
        agg_row = db.query(
            func.count(grouped.c.phash),
            func.coalesce(func.sum(grouped.c.group_bytes), 0),
            func.coalesce(func.sum(grouped.c.photo_count), 0),
        ).one()
        total_groups = int(agg_row[0] or 0)
        total_bytes = int(agg_row[1] or 0)
        total_photos = int(agg_row[2] or 0)
        if total_groups == 0:
            return 0, 0, 0, []

        phashes = [
            ph
            for (ph,) in db.query(grouped.c.phash)
            .order_by(grouped.c.phash.asc())
            .offset(offset)
            .limit(limit)
            .all()
        ]
        return total_groups, total_bytes, total_photos, phashes

    @staticmethod
    def get_duplicate_phashes(
        db: Session,
        limit: int,
        offset: int,
        excluded_prefixes: Optional[List[str]] = None,
    ) -> Tuple[int, List[str]]:
        total, _, _, phashes = PhotoRepository.get_duplicate_groups_page(
            db, limit=limit, offset=offset, excluded_prefixes=excluded_prefixes
        )
        return total, phashes

    @staticmethod
    def get_photos_by_phash(db: Session, phash: str) -> List[Photo]:
        return db.query(Photo).filter(Photo.phash == phash).all()

    @staticmethod
    def get_photos_by_phashes(db: Session, phashes: List[str]) -> List[Photo]:
        if not phashes:
            return []
        return db.query(Photo).filter(Photo.phash.in_(phashes)).all()

    @staticmethod
    def delete(db: Session, photo: Photo) -> None:
        db.delete(photo)
        db.commit()


photo_repo = PhotoRepository()
