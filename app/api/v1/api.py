from fastapi import APIRouter

from app.api.v1.endpoints import scan, cluster, photos

api_router = APIRouter()
api_router.include_router(scan.router, prefix="/scan", tags=["Scan"])
api_router.include_router(cluster.router, prefix="/cluster", tags=["Cluster"])
api_router.include_router(photos.router, prefix="/photos", tags=["Photos"])