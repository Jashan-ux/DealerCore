from fastapi import FastAPI
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title= settings.APP_NAME,
    docs_url = "/docs",
    redoc_url = "/redoc",
    openapi_url = "/openapi.json"
)

@app.get("/health", tags = ["Health"])
async def health_check():
    return {"status" : "healthy", "app": settings.APP_NAME}