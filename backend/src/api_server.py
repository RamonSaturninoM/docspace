"""FastAPI server for document management, ingestion, and chat."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, List

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

try:
    from .chat_engine import chat_with_documents
    from .document_store import build_document_store
    from .ingestion_engine import delete_document_vectors, index_document_file
except ImportError:
    from chat_engine import chat_with_documents
    from document_store import build_document_store
    from ingestion_engine import delete_document_vectors, index_document_file

try:
    from .ingestion_engine import extract_text
except ImportError:
    try:
        from ingestion_engine import extract_text
    except ModuleNotFoundError:
        extract_text = None


app = FastAPI(title="Docspace API", version="0.2")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_local_env(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        os.environ.setdefault(key, value.strip().strip("\"'"))


load_local_env(Path(__file__).resolve().parents[2] / ".env")
document_store = build_document_store(Path(__file__).resolve().parents[1])


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ChatRequest(BaseModel):
    message: str


class CommentRequest(BaseModel):
    author: str = "Anonymous"
    body: str


class DocumentUpdateRequest(BaseModel):
    pinned: bool


@app.post("/api/ingest")
async def ingest_files(files: List[UploadFile] = File(...)) -> JSONResponse:
    if extract_text is None:
        raise HTTPException(
            status_code=503,
            detail="Ingestion is temporarily unavailable.",
        )

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    with tempfile.TemporaryDirectory(prefix="docspace_ingest_") as temp_dir:
        temp_path = Path(temp_dir)
        saved = 0
        for item in files:
            if not item.filename:
                continue
            target = temp_path / Path(item.filename).name
            data = await item.read()
            if not data:
                continue
            target.write_bytes(data)
            saved += 1

        if saved == 0:
            raise HTTPException(status_code=400, detail="No valid files")

        extracted = 0
        failures: list[str] = []
        for path in temp_path.iterdir():
            try:
                if extract_text(path):
                    extracted += 1
            except Exception as exc:
                failures.append(f"{path.name}: {exc}")

    return JSONResponse(
        {
            "message": f"Processed {saved} file(s).",
            "indexable_files": extracted,
            "failures": failures,
        }
    )


@app.get("/healthz")
def healthz() -> JSONResponse:
    return JSONResponse({"ok": True})


@app.get("/api/documents")
def list_documents(
    q: str = Query(default=""),
    department: str | None = None,
    kind: str | None = None,
    pinned: bool | None = None,
    limit: int | None = None,
) -> JSONResponse:
    documents = document_store.list_documents(
        query=q,
        department=department,
        kind=kind,
        pinned=pinned,
        limit=limit,
    )
    return JSONResponse({"documents": documents})


@app.post("/api/documents")
async def create_document(
    file: UploadFile = File(...),
    title: Annotated[str, Form()] = "",
    department: Annotated[str, Form()] = "General",
    owner: Annotated[str, Form()] = "Unknown",
    description: Annotated[str, Form()] = "",
    pinned: Annotated[bool, Form()] = False,
) -> JSONResponse:
    filename = (file.filename or "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="Missing file name")

    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Uploaded file was empty")

    saved_file = document_store.storage.save_upload(filename, payload, file.content_type)
    document = document_store.create_document(
        saved_file=saved_file,
        title=title,
        department=department,
        owner=owner,
        description=description,
        pinned=pinned,
    )
    document_store.set_index_status(document["id"], status="processing", error="")
    try:
        result = index_document_file(document, saved_file.path)
        document = document_store.set_index_status(
            document["id"],
            status="ready",
            error="",
            chunk_count=result["chunk_count"],
            indexed_at=utc_now_iso(),
        )
    except Exception as exc:
        document = document_store.set_index_status(
            document["id"],
            status="failed",
            error=str(exc),
            chunk_count=0,
        )
    return JSONResponse(document, status_code=201)


@app.get("/api/documents/{document_id}")
def get_document(document_id: str) -> JSONResponse:
    document = document_store.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return JSONResponse(document)


@app.get("/api/documents/{document_id}/content")
def get_document_content(document_id: str):
    document = document_store.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    file_path = document_store.file_path(document_id)
    if file_path is None:
        raise HTTPException(status_code=404, detail="Document file not found")
    return FileResponse(
        file_path,
        media_type=document.get("mime_type", "application/octet-stream"),
        filename=document.get("filename", file_path.name),
    )


@app.patch("/api/documents/{document_id}")
def update_document(document_id: str, request: DocumentUpdateRequest) -> JSONResponse:
    document = document_store.set_pinned(document_id, request.pinned)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return JSONResponse(document)


@app.delete("/api/documents/{document_id}")
def delete_document(document_id: str) -> JSONResponse:
    document = document_store.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        delete_document_vectors(document_id)
    except Exception:
        pass
    deleted = document_store.delete_document(document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return JSONResponse({"deleted": True})


@app.post("/api/documents/{document_id}/index")
def reindex_document(document_id: str) -> JSONResponse:
    document = document_store.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    file_path = document_store.file_path(document_id)
    if file_path is None:
        raise HTTPException(status_code=404, detail="Document file not found")

    document_store.set_index_status(document_id, status="processing", error="")
    try:
        delete_document_vectors(document_id)
    except Exception:
        pass

    try:
        result = index_document_file(document, file_path)
        refreshed = document_store.set_index_status(
            document_id,
            status="ready",
            error="",
            chunk_count=result["chunk_count"],
            indexed_at=utc_now_iso(),
        )
    except Exception as exc:
        refreshed = document_store.set_index_status(
            document_id,
            status="failed",
            error=str(exc),
            chunk_count=0,
        )
    return JSONResponse(refreshed)


@app.post("/api/documents/{document_id}/comments")
def add_comment(document_id: str, request: CommentRequest) -> JSONResponse:
    if not request.body.strip():
        raise HTTPException(status_code=400, detail="Comment body cannot be empty")
    comment = document_store.add_comment(document_id, request.author, request.body)
    if comment is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return JSONResponse(comment, status_code=201)


@app.get("/api/dashboard/stats")
def dashboard_stats() -> JSONResponse:
    return JSONResponse(document_store.dashboard_stats())


@app.post("/api/chat")
def chat(request: ChatRequest) -> JSONResponse:
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    try:
        payload = chat_with_documents(message)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return JSONResponse(payload)


@app.post("/api/chat/respond")
def chat_respond(request: ChatRequest) -> JSONResponse:
    return chat(request)
