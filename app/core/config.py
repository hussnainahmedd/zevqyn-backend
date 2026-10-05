import os
import re
from dotenv import load_dotenv

load_dotenv()


def _normalize_supabase_url(raw: str) -> str:
    """Strip trailing API paths that the SDK appends automatically.

    Users sometimes copy the full REST URL (e.g.
    ``https://xxx.supabase.co/rest/v1/``) from the Supabase dashboard.
    The Python SDK expects just the base ``https://xxx.supabase.co``.
    """
    return re.sub(r"/rest/v\d+/?$", "", raw.rstrip("/"))


class Settings:
    """Application settings loaded from environment variables.

    Core endpoints (``/``, ``/health``) start without any credentials.
    Supabase-dependent operations validate configuration at call time
    and fail with a clear error if required variables are missing.
    """

    SUPABASE_URL: str = _normalize_supabase_url(os.getenv("SUPABASE_URL", ""))
    SUPABASE_PUBLISHABLE_KEY: str = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
    SUPABASE_SECRET_KEY: str = os.getenv("SUPABASE_SECRET_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # CORS — comma-separated origins, e.g. "https://zevqyn.com,http://localhost:3000"
    CORS_ORIGINS: list[str] = [
        o.strip()
        for o in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://localhost:8000",
        ).split(",")
        if o.strip()
    ]

    # Upload limits
    MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "10"))
    
    # Chunking
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1500"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "200"))
    
    # RAG Settings
    RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "8"))
    RAG_MATCH_THRESHOLD: float = float(os.getenv("RAG_MATCH_THRESHOLD", "0.70"))
    RAG_MAX_CONTEXT_CHARS: int = int(os.getenv("RAG_MAX_CONTEXT_CHARS", "20000"))
    GEMINI_GENERATION_MODEL: str = os.getenv("GEMINI_GENERATION_MODEL", "gemini-2.5-flash")

    # Admin panel — dedicated credential login for /api/v1/admin/*.
    # ADMIN_ID / ADMIN_PASSWORD seed the first admin row on startup (only
    # when the admin_users table is empty); the password can be changed
    # later from the admin UI. ADMIN_JWT_SECRET signs admin session tokens
    # and MUST be set to a long random value in production.
    ADMIN_ID: str = os.getenv("ADMIN_ID", "")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "")
    ADMIN_JWT_SECRET: str = os.getenv("ADMIN_JWT_SECRET", "")

    @property
    def max_upload_bytes(self) -> int:
        """Maximum upload size in bytes."""
        return self.MAX_UPLOAD_MB * 1024 * 1024

    @property
    def supabase_configured(self) -> bool:
        """Return True if the minimum Supabase variables are set."""
        return bool(self.SUPABASE_URL and self.SUPABASE_SECRET_KEY)


settings = Settings()
