import uvicorn
from app.core.config import settings

if __name__ == "__main__":
    print(f"Starting server at http://{settings.HOST}:{settings.PORT}")
    print(f"Swagger API Docs: http://{settings.HOST}:{settings.PORT}{settings.API_V1_STR}/docs")
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
