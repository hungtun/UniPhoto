from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

db_url = settings.get_database_url

# Khởi tạo engine kết nối MySQL kèm Connection Pool
engine = create_engine(
    settings.get_database_url,
    echo=False,
    pool_pre_ping=True,   # Tự kiểm tra kết nối còn sống không trước khi thực thi truy vấn
    pool_recycle=3600,    # Tái tạo kết nối sau 1 giờ để tránh MySQL wait_timeout
    pool_size=10,         # Số kết nối thường trực trong pool
    max_overflow=20,      # Số kết nối tối đa có thể mở thêm khi tải cao
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency cung cấp db session cho mỗi request và tự động đóng khi hoàn tất."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Khởi tạo bảng trong cơ sở dữ liệu nếu chưa tồn tại."""
    try:
        Base.metadata.create_all(bind=engine)
        print("Database tables initialized successfully.")
    except Exception as e:
        print(f"Lưu ý: Chưa thể kết nối hoặc khởi tạo bảng trên MySQL ({e}).")
        print("Vui lòng đảm bảo MySQL Server đang chạy và Database đã được tạo trước.")
