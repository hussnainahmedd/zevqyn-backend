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

    @property
    def max_upload_bytes(self) -> int:
        """Maximum upload size in bytes."""
        return self.MAX_UPLOAD_MB * 1024 * 1024

    @property
    def supabase_configured(self) -> bool:
        """Return True if the minimum Supabase variables are set."""
        return bool(self.SUPABASE_URL and self.SUPABASE_SECRET_KEY)


settings = Settings()
