"""Document text chunking service."""

from __future__ import annotations

from app.core.config import settings
from app.models.chunking import DocumentChunk
from app.models.extraction import ExtractedDocument


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Deterministically chunk text by approximate character limit with overlap.
    
    Avoids cutting words where possible by backing up to spaces.
    """
    if not text:
        return []
        
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = start + chunk_size
        
        # If this is the last chunk, just take the rest
        if end >= text_len:
            chunks.append(text[start:].strip())
            break
            
        # Try to find a natural break (newline or space) near the end limit
        # Look backwards from 'end' for up to 100 characters to avoid word splitting
        break_idx = end
        for i in range(end, max(start, end - 100), -1):
            if i < text_len and text[i] in ("\n", " ", "\t"):
                break_idx = i
                break
                
        # If we couldn't find a space, just hard-cut at 'end'
        chunk = text[start:break_idx].strip()
        if chunk:
            chunks.append(chunk)
            
        # Advance start, accounting for overlap
        start = break_idx - chunk_overlap
        
        # Real fix for infinite loop prevention:
        new_start = break_idx - chunk_overlap
        # We must advance. If overlap pushes us backwards or we don't move, force advance.
        # But we compare against the original `start` variable of this iteration.
        old_start = start
        if new_start <= old_start:
            start = break_idx if break_idx > old_start else old_start + 1
        else:
            start = new_start

    return [c for c in chunks if c]


def chunk_document(document: ExtractedDocument) -> list[DocumentChunk]:
    """Generate deterministic chunks from an extracted document.
    
    Critically, chunks are generated *per extraction unit* to preserve
    accurate citations (e.g., PDF page numbers). Chunks never span
    across multiple extraction units.
    """
    chunks = []
    chunk_idx = 0
    
    for unit in document.units:
        unit_text = unit.text.strip()
        if not unit_text:
            continue
            
        text_chunks = chunk_text(
            unit_text, 
            chunk_size=settings.CHUNK_SIZE, 
            chunk_overlap=settings.CHUNK_OVERLAP
        )
        
        for text in text_chunks:
            chunks.append(DocumentChunk(
                chunk_index=chunk_idx,
                content=text,
                page_number=unit.page_number,
                source_label=unit.source_label,
                metadata={
                    "file_type": document.file_type,
                    "extraction_unit_index": unit.index
                }
            ))
            chunk_idx += 1
            
    return chunks
