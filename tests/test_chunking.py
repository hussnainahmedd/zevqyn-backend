"""Unit tests for document chunking."""

from __future__ import annotations

from app.models.extraction import ExtractedDocument, ExtractedUnit
from app.services.chunking import chunk_text, chunk_document
import uuid


def test_chunk_text_short():
    text = "Short text"
    chunks = chunk_text(text, chunk_size=1500, chunk_overlap=200)
    assert len(chunks) == 1
    assert chunks[0] == "Short text"


def test_chunk_text_long_no_empty_chunks():
    # 20 words, we'll set chunk size very small
    text = "A B C D E F G H I J K L M N O P Q R S T"
    chunks = chunk_text(text, chunk_size=10, chunk_overlap=2)
    assert len(chunks) > 1
    assert all(len(c) > 0 for c in chunks)
    assert chunks[0] == "A B C D E" # roughly
    
    # Reassemble to ensure we didn't drop anything major, though exact match isn't required due to overlaps
    # Instead, just verify order and sequential overlapping logic
    assert "A B" in chunks[0]
    assert "S T" in chunks[-1]


def test_chunk_document_preserves_citations():
    doc = ExtractedDocument(
        document_id=uuid.uuid4(),
        original_filename="test.pdf",
        file_type=".pdf",
        unit_count=2,
        character_count=100,
        units=[
            ExtractedUnit(index=0, text="Page 1 text", page_number=1, source_label="Page 1"),
            ExtractedUnit(index=1, text="Page 2 text", page_number=2, source_label="Page 2"),
        ]
    )
    
    chunks = chunk_document(doc)
    assert len(chunks) == 2
    
    assert chunks[0].chunk_index == 0
    assert chunks[0].page_number == 1
    assert chunks[0].source_label == "Page 1"
    
    assert chunks[1].chunk_index == 1
    assert chunks[1].page_number == 2
    assert chunks[1].source_label == "Page 2"


def test_chunk_document_sequential_indices():
    # If a unit produces multiple chunks, indices must not reset
    long_text = "Word " * 1000
    doc = ExtractedDocument(
        document_id=uuid.uuid4(),
        original_filename="test.txt",
        file_type=".txt",
        unit_count=1,
        character_count=5000,
        units=[
            ExtractedUnit(index=0, text=long_text, source_label="Document"),
        ]
    )
    
    chunks = chunk_document(doc)
    assert len(chunks) > 1
    
    indices = [c.chunk_index for c in chunks]
    assert indices == list(range(len(chunks)))
    
    # Metadata preserved
    for c in chunks:
        assert c.page_number is None
        assert c.source_label == "Document"
        assert c.metadata["file_type"] == ".txt"
