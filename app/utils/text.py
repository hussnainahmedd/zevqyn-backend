"""Text normalization utilities."""

from __future__ import annotations

import re


def normalize_text(text: str) -> str:
    """Safely normalize text for processing without losing meaning.
    
    - Removes null characters
    - Normalizes line endings to LF
    - Reduces excessive blank lines
    - Removes trailing line whitespace
    """
    if not text:
        return ""
        
    # Remove null characters
    text = text.replace("\x00", "")
    
    # Normalize CRLF/CR to LF
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    
    # Remove trailing whitespace on each line
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    
    # Collapse multiple blank lines to at most two
    text = re.sub(r"\n{3,}", "\n\n", text)
    
    return text.strip()
