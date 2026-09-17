"""Unit tests for Gemini embedding service."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.embeddings import embed_document, embed_query


@patch("app.services.embeddings.get_gemini_client")
def test_embed_document(mock_get_client):
    mock_client = mock_get_client.return_value
    
    # Setup mock response
    mock_res = MagicMock()
    mock_emb1 = MagicMock()
    mock_emb1.values = [0.1] * 768
    mock_emb2 = MagicMock()
    mock_emb2.values = [0.2] * 768
    mock_res.embeddings = [mock_emb1, mock_emb2]
    
    mock_client.models.embed_content.return_value = mock_res
    
    texts = ["Chunk 1", "Chunk 2"]
    result = embed_document(texts)
    
    assert len(result) == 2
    assert len(result[0]) == 768
    
    # Verify task type
    args, kwargs = mock_client.models.embed_content.call_args
    assert kwargs["config"].task_type == "RETRIEVAL_DOCUMENT"
    assert kwargs["config"].output_dimensionality == 768


@patch("app.services.embeddings.get_gemini_client")
def test_embed_query(mock_get_client):
    mock_client = mock_get_client.return_value
    
    mock_res = MagicMock()
    mock_emb1 = MagicMock()
    mock_emb1.values = [0.1] * 768
    mock_res.embeddings = [mock_emb1]
    
    mock_client.models.embed_content.return_value = mock_res
    
    result = embed_query("What is X?")
    
    assert len(result) == 768
    
    args, kwargs = mock_client.models.embed_content.call_args
    assert kwargs["config"].task_type == "RETRIEVAL_QUERY"


@patch("app.services.embeddings.get_gemini_client")
def test_invalid_dimension_raises(mock_get_client):
    mock_client = mock_get_client.return_value
    
    mock_res = MagicMock()
    mock_emb1 = MagicMock()
    mock_emb1.values = [0.1] * 100 # Invalid length
    mock_res.embeddings = [mock_emb1]
    
    mock_client.models.embed_content.return_value = mock_res
    
    with pytest.raises(HTTPException) as exc:
        embed_query("query")
        
    assert exc.value.status_code == 502
    assert "Unexpected embedding dimension" in exc.value.detail


@patch("app.services.embeddings.get_gemini_client")
def test_api_failure_raises(mock_get_client):
    mock_client = mock_get_client.return_value
    mock_client.models.embed_content.side_effect = Exception("API Quota Error")
    
    with pytest.raises(HTTPException) as exc:
        embed_query("query")
        
    assert exc.value.status_code == 502
    assert "Failed to generate embeddings" in exc.value.detail
