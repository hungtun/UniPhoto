from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.api.v1.endpoints import scan, cluster
from app.core.config import settings
from app.core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi tạo bảng SQLite (WAL mode) khi server khởi động
    init_db()
    yield


def create_app() -> FastAPI:
    """
    Application factory để khởi tạo và cấu hình ứng dụng FastAPI.
    """
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=f"{settings.API_V1_STR}/docs",
        redoc_url=f"{settings.API_V1_STR}/redoc",
        description="FastAPI Backend quản lý & lọc trùng ảnh thông minh với pHash, EXIF và AI MobileNetV2.",
        lifespan=lifespan,
    )

    # Cấu hình CORS Middleware
    if settings.BACKEND_CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.BACKEND_CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Đăng ký router chính /api/v1
    app.include_router(api_router, prefix=settings.API_V1_STR)

    # Đăng ký alias trực tiếp cho POST /api/scan và POST /api/cluster
    app.include_router(scan.router, prefix="/api/scan", tags=["Scan Direct"])
    app.include_router(cluster.router, prefix="/api/cluster", tags=["Cluster Direct"])

    # Health check endpoint cho Tauri sidecar và bộ kiểm thử tự động
    @app.get(f"{settings.API_V1_STR}/health", tags=["Health Check"])
    def health_check():
        return {
            "status": "ok",
            "version": settings.VERSION,
            "port": settings.PORT,
        }

    # Root endpoint để kiểm tra nhanh trạng thái server
    @app.get("/", tags=["Health Check"])
    def root():
        return {
            "status": "ok",
            "message": "Welcome to UniPhoto API",
            "docs": f"{settings.API_V1_STR}/docs",
            "scan_endpoint": "/api/scan",
            "cluster_endpoint": "/api/cluster",
            "version": settings.VERSION,
        }

    return app


app = create_app()
