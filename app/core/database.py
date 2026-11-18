from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

# Khởi tạo engine kết nối SQLite (hỗ trợ đa luồng cho FastAPI)
engine = create_engine(
    settings.get_database_url,
    connect_args={"check_same_thread": False},
    echo=False,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    # Bật chế độ WAL giúp đọc/ghi đồng thời mượt mà và tăng tốc độ ghi trên ổ cứng
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency cung cấp db session cho mỗi request và tự động đóng khi hoàn tất."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _migrate_sqlite_columns() -> None:
    """Tự động bổ sung các cột chấm điểm chất lượng ảnh nếu DB cũ chưa có."""
    new_photo_columns = {
        "width": "INTEGER",
        "height": "INTEGER",
        "quality_score": "FLOAT",
        "sharpness_score": "FLOAT",
        "exposure_score": "FLOAT",
        "contrast_score": "FLOAT",
        "aesthetic_score": "FLOAT",
        "composition_score": "FLOAT",
        "face_score": "FLOAT",
        "pose_score": "FLOAT",
        "tilt_angle": "FLOAT",
        "has_closed_eyes": "INTEGER",
        "aesthetic_tags": "VARCHAR(500)",
    }
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(photos);")).fetchall()
        if not rows:
            return
        existing_cols = {row[1] for row in rows}
        for col_name, col_type in new_photo_columns.items():
            if col_name not in existing_cols:
                conn.execute(
                    text(f"ALTER TABLE photos ADD COLUMN {col_name} {col_type};")
                )


def init_db():
    """Tự động khởi tạo file SQLite, các bảng và nâng cấp cột nếu chưa tồn tại."""
    from app.models import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_sqlite_columns()
    print(f"SQLite Database initialized at: {settings.SQLITE_DB_PATH}", flush=True)
