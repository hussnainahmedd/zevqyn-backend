from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import router as v1_router
from app.api.workspaces import router as workspaces_router
from app.core.config import settings

app = FastAPI(
    title="ZEVQYN Backend",
    description="AI Research + Career Workspace API",
    version="0.1.0",
)

# CORS — configurable via CORS_ORIGINS env var.
# Development default allows localhost; update for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────
app.include_router(v1_router)
app.include_router(workspaces_router)


@app.get("/")
async def root():
    return {
        "name": "ZEVQYN",
        "status": "online",
        "message": "ZEVQYN backend is running",
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}
