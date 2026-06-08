"""Student document upload, preview, and collection management endpoints."""

import asyncio
import hashlib
import os
import shutil
import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docere.api.memory import _classify_document
from docere.config import settings
from docere.core.memory.student_documents import ALLOWED_EXTENSIONS, collection_name_for
from docere.dependencies import get_current_user_id, get_db, get_qdrant

logger = structlog.get_logger()

router = APIRouter()


# ── Response Models ──


class DocumentUploadResponse(BaseModel):
    doc_id: str
    filename: str
    status: str
    extracted_text: str
    page_count: int | None


class DocumentSummary(BaseModel):
    id: str
    filename: str
    status: str
    chunk_count: int
    page_count: int | None
    file_size_bytes: int
    created_at: str
    error_message: str | None
    doc_type: str | None = None


class DocumentDetail(BaseModel):
    id: str
    filename: str
    status: str
    chunk_count: int
    page_count: int | None
    file_size_bytes: int
    extracted_text: str | None
    created_at: str
    error_message: str | None
    doc_type: str | None = None
    has_file: bool = False


class DocumentStatusResponse(BaseModel):
    id: str
    status: str
    chunk_count: int
    page_count: int | None
    error_message: str | None


class UrlUploadRequest(BaseModel):
    url: str
    course_id: str


# ── Helpers ──


def _stored_file_path(doc_id: str, filename: str) -> str:
    """Persistent storage path for original file: data/student_docs/{doc_id}/{filename}."""
    return os.path.join(settings.student_doc_storage_dir, doc_id, filename)


def _persist_original(doc_id: str, filename: str, file_bytes: bytes) -> str:
    """Save original file to persistent storage. Returns the stored path."""
    path = _stored_file_path(doc_id, filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(file_bytes)
    return path


async def _save_and_parse(file_bytes: bytes, filename: str) -> tuple[str, int | None]:
    """Save file to temp dir, parse text, clean up. Returns (text, page_count)."""
    from docere.core.memory.student_documents import StudentDocumentManager
    from docere.integrations.vector_db.qdrant import QdrantStore

    tmp_id = uuid.uuid4()
    upload_dir = os.path.join(settings.student_doc_upload_dir, str(tmp_id))
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, filename)
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    try:
        manager = StudentDocumentManager(QdrantStore())
        text, page_count = await manager.parse_document(file_path)
    finally:
        shutil.rmtree(upload_dir, ignore_errors=True)

    return text, page_count


async def _validate_upload(
    db: AsyncSession, user_id: uuid.UUID, course_id: str, file_bytes: bytes
) -> str:
    """Validate doc count and dedup. Returns content_hash."""
    from docere.models.document import StudentDocument

    count_result = await db.execute(
        select(sa_func.count(StudentDocument.id)).where(
            StudentDocument.student_id == user_id,
            StudentDocument.course_id == uuid.UUID(course_id),
            StudentDocument.status != "failed",
        )
    )
    if (count_result.scalar() or 0) >= settings.student_doc_max_per_course:
        raise HTTPException(status_code=400, detail="Maximum documents per course reached")

    content_hash = hashlib.sha256(file_bytes).hexdigest()
    existing = await db.execute(
        select(StudentDocument).where(
            StudentDocument.student_id == user_id,
            StudentDocument.course_id == uuid.UUID(course_id),
            StudentDocument.content_hash == content_hash,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="This file has already been uploaded")

    return content_hash


async def _embed_and_update(doc_id: str, student_id: str, course_id: str, text: str) -> None:
    """Background task: chunk, embed, and update DB status."""
    from docere.core.memory.student_documents import StudentDocumentManager
    from docere.dependencies import async_session

    async with async_session() as db:
        from docere.models.document import StudentDocument

        doc = await db.get(StudentDocument, uuid.UUID(doc_id))
        if not doc:
            return

        doc.status = "processing"
        doc.processing_started_at = datetime.now(UTC)
        await db.commit()

        try:
            qdrant = get_qdrant()
            manager = StudentDocumentManager(qdrant)
            chunk_count = await manager.embed_document(doc_id, student_id, course_id, text)
            doc.status = "completed"
            doc.chunk_count = chunk_count
            doc.processing_completed_at = datetime.now(UTC)
        except Exception as e:
            logger.error("Document embedding failed", doc_id=doc_id, error=str(e))
            doc.status = "failed"
            doc.error_message = str(e)[:500]

        await db.commit()


# ── Endpoints ──


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    course_id: str = Form(...),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Upload and parse a document. Returns extracted text for preview."""
    from docere.models.document import StudentDocument

    _, ext = os.path.splitext(file.filename or "")
    if ext.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    file_bytes = await file.read()
    max_bytes = settings.student_doc_max_file_size_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max: {settings.student_doc_max_file_size_mb}MB",
        )

    content_hash = await _validate_upload(db, user_id, course_id, file_bytes)

    # Parse text immediately
    filename = file.filename or "document"
    text, page_count = await _save_and_parse(file_bytes, filename)

    # Save to DB with extracted text
    doc_id = uuid.uuid4()
    collection = collection_name_for(str(user_id), course_id)

    # Persist original file for rendering
    _persist_original(str(doc_id), filename, file_bytes)

    doc = StudentDocument(
        id=doc_id,
        student_id=user_id,
        course_id=uuid.UUID(course_id),
        filename=filename,
        original_filename=filename,
        file_size_bytes=len(file_bytes),
        mime_type=file.content_type or "application/octet-stream",
        content_hash=content_hash,
        extracted_text=text,
        status="uploaded",
        page_count=page_count,
        collection_name=collection,
    )
    db.add(doc)
    await db.commit()

    return DocumentUploadResponse(
        doc_id=str(doc_id),
        filename=filename,
        status="uploaded",
        extracted_text=text,
        page_count=page_count,
    )


@router.post("/upload-url", response_model=DocumentUploadResponse)
async def upload_document_from_url(
    request: UrlUploadRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Download a document from URL, parse it, return text for preview."""
    from urllib.parse import unquote, urlparse

    import httpx as httpx_client

    from docere.models.document import StudentDocument

    parsed = urlparse(request.url)
    filename = os.path.basename(unquote(parsed.path)) or "document.pdf"
    _, ext = os.path.splitext(filename)
    ext = ext.lower()
    if not ext:
        ext = ".pdf"
        filename += ext
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    max_bytes = settings.student_doc_max_file_size_mb * 1024 * 1024
    try:
        async with httpx_client.AsyncClient(follow_redirects=True, timeout=120.0) as client:
            resp = await client.get(request.url)
            resp.raise_for_status()
            file_bytes = resp.content
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Download failed: {str(e)[:200]}")

    if len(file_bytes) > max_bytes:
        raise HTTPException(status_code=400, detail="File too large")
    if len(file_bytes) < 100:
        raise HTTPException(status_code=400, detail="File is empty or too small")

    content_hash = await _validate_upload(db, user_id, request.course_id, file_bytes)

    # Parse text immediately
    text, page_count = await _save_and_parse(file_bytes, filename)

    # Save to DB
    doc_id = uuid.uuid4()
    collection = collection_name_for(str(user_id), request.course_id)
    mime_type = resp.headers.get("content-type", "application/octet-stream").split(";")[0]

    # Persist original file for rendering
    _persist_original(str(doc_id), filename, file_bytes)

    doc = StudentDocument(
        id=doc_id,
        student_id=user_id,
        course_id=uuid.UUID(request.course_id),
        filename=filename,
        original_filename=filename,
        file_size_bytes=len(file_bytes),
        mime_type=mime_type,
        content_hash=content_hash,
        extracted_text=text,
        status="uploaded",
        page_count=page_count,
        collection_name=collection,
    )
    db.add(doc)
    await db.commit()

    return DocumentUploadResponse(
        doc_id=str(doc_id),
        filename=filename,
        status="uploaded",
        extracted_text=text,
        page_count=page_count,
    )


@router.post("/{doc_id}/confirm", response_model=DocumentStatusResponse)
async def confirm_document(
    doc_id: str,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Add document to collection: chunks and embeds in the background."""
    from docere.models.document import StudentDocument

    doc = await db.get(StudentDocument, uuid.UUID(doc_id))
    if not doc or doc.student_id != user_id:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.status != "uploaded":
        raise HTTPException(status_code=400, detail=f"Document is already {doc.status}")
    if not doc.extracted_text:
        raise HTTPException(status_code=400, detail="No extracted text available")

    # Fire-and-forget background embedding
    asyncio.create_task(
        _embed_and_update(str(doc.id), str(doc.student_id), str(doc.course_id), doc.extracted_text)
    )

    return DocumentStatusResponse(
        id=str(doc.id),
        status="processing",
        chunk_count=0,
        page_count=doc.page_count,
        error_message=None,
    )


@router.get("", response_model=list[DocumentSummary])
async def list_documents(
    course_id: str | None = None,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List documents. If course_id given, filter by course. Otherwise all."""
    from docere.models.document import StudentDocument

    query = select(StudentDocument).where(StudentDocument.student_id == user_id)
    if course_id:
        query = query.where(StudentDocument.course_id == uuid.UUID(course_id))
    query = query.order_by(StudentDocument.created_at.desc())

    result = await db.execute(query)
    docs = result.scalars().all()

    return [
        DocumentSummary(
            id=str(d.id),
            filename=d.filename,
            status=d.status,
            chunk_count=d.chunk_count,
            page_count=d.page_count,
            file_size_bytes=d.file_size_bytes,
            created_at=d.created_at.isoformat(),
            error_message=d.error_message,
            doc_type=_classify_document(
                d.filename,
                d.mime_type,
                extracted_text=d.extracted_text,
                page_count=d.page_count,
            ),
        )
        for d in docs
    ]


@router.get("/{doc_id}", response_model=DocumentDetail)
async def get_document(
    doc_id: str,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get full document detail including extracted text."""
    from docere.models.document import StudentDocument

    doc = await db.get(StudentDocument, uuid.UUID(doc_id))
    if not doc or doc.student_id != user_id:
        raise HTTPException(status_code=404, detail="Document not found")

    stored_path = _stored_file_path(doc_id, doc.filename)
    return DocumentDetail(
        id=str(doc.id),
        filename=doc.filename,
        status=doc.status,
        chunk_count=doc.chunk_count,
        page_count=doc.page_count,
        file_size_bytes=doc.file_size_bytes,
        extracted_text=doc.extracted_text,
        created_at=doc.created_at.isoformat(),
        error_message=doc.error_message,
        doc_type=_classify_document(
            doc.filename,
            doc.mime_type,
            extracted_text=doc.extracted_text,
            page_count=doc.page_count,
        ),
        has_file=os.path.isfile(stored_path),
    )


@router.get("/{doc_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    doc_id: str,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Check processing status of a document."""
    from docere.models.document import StudentDocument

    doc = await db.get(StudentDocument, uuid.UUID(doc_id))
    if not doc or doc.student_id != user_id:
        raise HTTPException(status_code=404, detail="Document not found")

    return DocumentStatusResponse(
        id=str(doc.id),
        status=doc.status,
        chunk_count=doc.chunk_count,
        page_count=doc.page_count,
        error_message=doc.error_message,
    )


@router.get("/{doc_id}/file")
async def get_document_file(
    doc_id: str,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Serve the original uploaded file for in-browser rendering."""
    from fastapi.responses import FileResponse

    from docere.models.document import StudentDocument

    doc = await db.get(StudentDocument, uuid.UUID(doc_id))
    if not doc or doc.student_id != user_id:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = _stored_file_path(doc_id, doc.filename)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Original file not available")

    return FileResponse(
        path=file_path,
        media_type=doc.mime_type or "application/octet-stream",
        filename=doc.filename,
    )


@router.delete("/{doc_id}", status_code=204)
async def delete_document(
    doc_id: str,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Delete a document and its vectors."""
    from docere.core.memory.student_documents import StudentDocumentManager
    from docere.models.document import StudentDocument

    doc = await db.get(StudentDocument, uuid.UUID(doc_id))
    if not doc or doc.student_id != user_id:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.status == "completed":
        qdrant = get_qdrant()
        manager = StudentDocumentManager(qdrant)
        await manager.delete_document(str(doc.id), str(doc.student_id), str(doc.course_id))

    # Clean up stored file
    stored_dir = os.path.join(settings.student_doc_storage_dir, doc_id)
    shutil.rmtree(stored_dir, ignore_errors=True)

    await db.delete(doc)
    await db.commit()
