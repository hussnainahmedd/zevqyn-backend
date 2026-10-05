"""Shared per-IP rate limiter (slowapi).

Import from here — never from app.main — to avoid circular imports.
"""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
