from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="ZEVQYN Backend",
    description="AI Research + Career Workspace API",
    version="0.1.0",
)

# CORS — allow the WordPress frontend (update origins for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
