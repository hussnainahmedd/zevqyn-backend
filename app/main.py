from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1 import router as v1_router
from app.api.workspaces import router as workspaces_router
from app.api.research import router as research_router
from app.api.projects import router as projects_router
from app.api.career import router as career_router
from app.api.resumes import router as resumes_router
from app.api.portfolios import router as portfolios_router
from app.api.profile import router as profile_router
from app.api.contact import router as contact_router
from app.api.documents import router as documents_router
from app.core.config import settings
from app.core.rate_limit import limiter

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

# ── Rate limiting (per client IP) ─────────────────────────────────────────
# Public endpoints carry their own limits at the route level.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ── Routers ──────────────────────────────────────────────────────────────
app.include_router(v1_router)
app.include_router(workspaces_router)
app.include_router(documents_router)
app.include_router(research_router)
app.include_router(projects_router)
app.include_router(career_router)
app.include_router(resumes_router)
app.include_router(portfolios_router)
app.include_router(profile_router)
app.include_router(contact_router)


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
