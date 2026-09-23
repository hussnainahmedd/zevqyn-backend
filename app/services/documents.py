"""Document service logic."""

from __future__ import annotations

import uuid
from typing import BinaryIO
from uuid import UUID

from fastapi import HTTPException, status, UploadFile

from app.core.config import settings
from app.core.supabase import get_admin_client
from app.models.document import DocumentResponse, DocumentDownloadResponse
from app.services.workspaces import get_workspace
from app.utils.files import sanitize_filename, validate_extension, validate_content_type

BUCKET_NAME = "research-documents"


def upload_document(user_id: UUID, workspace_id: UUID, file: UploadFile) -> DocumentResponse:
    """Securely upload a document to Supabase Storage and create metadata record."""
    # 1. Verify workspace ownership
    get_workspace(user_id, workspace_id)
    
    # 2. Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename missing")
        
    try:
        ext = validate_extension(file.filename)
    except ValueError as e:
        raise HTTPException(status_code=415, detail=str(e))
        
    if not validate_content_type(file.content_type, ext):
        raise HTTPException(status_code=415, detail="MIME type does not match extension")
        
    # Read file content to check size
    content = file.file.read()
    file_size = len(content)
    
    if file_size > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File exceeds maximum allowed size ({settings.MAX_UPLOAD_MB} MB)",
        )
        
    if file_size == 0:
        raise HTTPException(status_code=400, detail="Empty file")
        
    safe_filename = sanitize_filename(file.filename)
    
    # Generate storage path: user_uuid/workspace_uuid/document_uuid/safe_filename
    document_uuid = uuid.uuid4()
    storage_path = f"{user_id}/{workspace_id}/{document_uuid}/{safe_filename}"
    
    client = get_admin_client()
    
    # 3. Upload to Storage
    try:
        # Check if bucket exists (useful if testing or if not setup)
        # But we assume bucket "research-documents" exists as per instructions
        res = client.storage.from_(BUCKET_NAME).upload(
            path=storage_path,
            file=content,
            file_options={"content-type": file.content_type or "application/octet-stream"}
        )
        # Check for upload failure (storage3 library usually raises exceptions on error, but let's be careful)
        if hasattr(res, 'error') and res.error:
            raise Exception(f"Storage upload error: {res.error}")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to upload file to storage system"
        )
        
    # 4. Insert metadata
    doc_data = {
        "id": str(document_uuid),
        "user_id": str(user_id),
        "workspace_id": str(workspace_id),
        "filename": safe_filename,
        "original_filename": file.filename,
        "storage_path": storage_path,
        "file_type": ext.lstrip("."),
        "file_size": file_size,
        "status": "uploaded",
    }
    
    try:
        db_res = client.table("documents").insert(doc_data).execute()
        if not db_res.data:
            raise Exception("No data returned from database insert")
        return DocumentResponse(**db_res.data[0])
    except Exception as e:
        # Roll back uploaded file if metadata insert fails
        try:
            client.storage.from_(BUCKET_NAME).remove([storage_path])
        except Exception:
            pass

        print("DOCUMENT METADATA INSERT ERROR:", repr(e))

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save document metadata: {str(e)}"
        )


def get_documents(user_id: UUID, workspace_id: UUID) -> list[DocumentResponse]:
    """Get all documents in a workspace for the user."""
    # Verify workspace ownership first
    get_workspace(user_id, workspace_id)
    
    client = get_admin_client()
    response = client.table("documents").select("*").eq("workspace_id", str(workspace_id)).eq("user_id", str(user_id)).execute()
    
    return [DocumentResponse(**d) for d in response.data]


def get_document(user_id: UUID, workspace_id: UUID, document_id: UUID) -> DocumentResponse:
    """Get a specific document if owned by the user."""
    client = get_admin_client()
    
    # We explicitly check both workspace_id and user_id for extra security
    response = client.table("documents").select("*").eq("id", str(document_id)).eq("workspace_id", str(workspace_id)).eq("user_id", str(user_id)).execute()
    
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
        
    return DocumentResponse(**response.data[0])


def delete_document(user_id: UUID, workspace_id: UUID, document_id: UUID) -> None:
    """Delete a document and its associated file in storage."""
    # Verify document ownership and get storage path
    doc = get_document(user_id, workspace_id, document_id)
    
    # We need the storage_path which isn't in DocumentResponse
    client = get_admin_client()
    db_res = client.table("documents").select("storage_path").eq("id", str(document_id)).execute()
    
    if not db_res.data:
        # Shouldn't happen if get_document succeeded, but just in case
        raise HTTPException(status_code=404, detail="Document not found")
        
    storage_path = db_res.data[0]["storage_path"]
    
    # Delete from storage
    try:
        client.storage.from_(BUCKET_NAME).remove([storage_path])
    except Exception:
        # We might want to log this in a real app, but for now we continue
        # and allow DB deletion even if storage fails, otherwise users might
        # get stuck unable to delete a document record.
        pass
        
    # Delete from DB
    response = client.table("documents").delete().eq("id", str(document_id)).eq("user_id", str(user_id)).execute()
    
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document metadata",
        )


def generate_download_url(user_id: UUID, workspace_id: UUID, document_id: UUID) -> DocumentDownloadResponse:
    """Generate a short-lived signed URL for downloading a document."""
    doc = get_document(user_id, workspace_id, document_id)
    
    client = get_admin_client()
    db_res = client.table("documents").select("storage_path").eq("id", str(document_id)).execute()
    
    if not db_res.data:
        raise HTTPException(status_code=404, detail="Document not found")
        
    storage_path = db_res.data[0]["storage_path"]
    
    try:
        # Create a signed URL valid for 60 seconds
        expires_in = 60
        signed_url = client.storage.from_(BUCKET_NAME).create_signed_url(storage_path, expires_in)
        
        # storage3 create_signed_url returns a dict like {'signedURL': 'https:...'}
        url = signed_url.get("signedURL") or signed_url.get("signedUrl")
        
        if not url:
            raise Exception("Failed to get URL from Supabase response")
            
        return DocumentDownloadResponse(url=url, expires_in_seconds=expires_in)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate download URL",
        )


def get_user_documents(
    user_id: UUID,
    workspace_id: UUID | None = None,
    file_type: str | None = None,
    status_filter: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[DocumentResponse]:
    """List documents owned by the user with optional filters and pagination."""
    client = get_admin_client()
    query = (
        client.table("documents")
        .select("*")
        .eq("user_id", str(user_id))
    )

    if workspace_id is not None:
        query = query.eq("workspace_id", str(workspace_id))

    if file_type is not None and file_type.strip():
        clean_ft = file_type.strip().lower().lstrip(".")
        query = query.eq("file_type", clean_ft)

    if status_filter is not None and status_filter.strip():
        query = query.eq("status", status_filter.strip())

    if search is not None and search.strip():
        query = query.ilike("original_filename", f"%{search.strip()}%")

    query = query.order("created_at", desc=True)

    if limit > 0:
        query = query.range(offset, offset + limit - 1)

    try:
        response = query.execute()
        return [DocumentResponse(**d) for d in (response.data or [])]
    except Exception as e:
        print("GET USER DOCUMENTS ERROR:", repr(e), flush=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch documents",
        )
