"""File validation and sanitisation utilities."""

from __future__ import annotations

import os
import re

# Allowed file types: extension -> list of acceptable MIME types
ALLOWED_TYPES: dict[str, list[str]] = {
    ".pdf": ["application/pdf"],
    ".docx": [
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ],
    ".txt": ["text/plain"],
    ".md": ["text/markdown", "text/plain", "text/x-markdown", "application/octet-stream"],
}

ALLOWED_EXTENSIONS: set[str] = set(ALLOWED_TYPES.keys())


def sanitize_filename(filename: str) -> str:
    """Return a safe, flat filename with no path components.

    * Strips directory separators and path traversal sequences.
    * Removes characters that are unsafe on common filesystems.
    * Collapses whitespace.
    * Falls back to 'unnamed' if nothing usable remains.
    """
    # Take only the basename (handles both / and \\)
    name = os.path.basename(filename)
    # Remove path-traversal fragments
    name = name.replace("..", "")
    # Keep only safe characters: alphanumeric, hyphen, underscore, dot, space
    name = re.sub(r"[^\w.\- ]", "_", name)
    # Collapse multiple underscores/spaces
    name = re.sub(r"[_ ]{2,}", "_", name).strip("_ ")
    if not name or name.startswith("."):
        name = "unnamed"
    return name


def validate_extension(filename: str) -> str:
    """Return the lowercased extension if allowed, else raise ValueError."""
    _, ext = os.path.splitext(filename)
    ext = ext.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{ext}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    return ext


def validate_content_type(content_type: str | None, extension: str) -> bool:
    """Check that the declared MIME type is plausible for the extension.

    Returns True if acceptable.  We are lenient because clients
    sometimes send generic types like application/octet-stream.
    """
    if not content_type:
        return True  # no MIME declared — rely on extension
    acceptable = ALLOWED_TYPES.get(extension, [])
    # Also accept the generic octet-stream fallback
    return content_type in acceptable or content_type == "application/octet-stream"
