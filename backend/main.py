from fastapi import FastAPI, UploadFile, File, Form
import os
from pathlib import Path
from pydantic import BaseModel

from database import (
    create_db_and_tables,
    add_document,
    add_uploaded_document,
    list_documents,
    get_document_by_id,
    delete_document_by_id,
)

app = FastAPI()

@app.on_event("startup")
def on_startup():
    create_db_and_tables()

@app.get("/")
def root():
    return {"message": "Backend is running"}

@app.get("/health")
def health():
    return {"status": "ok"}

class DocumentCreate(BaseModel):
    filename: str
    department: str
    role: str

@app.post("/documents")
def create_document(payload: DocumentCreate):
    doc = add_document(
        filename=payload.filename,
        department=payload.department,
        role=payload.role,
    )
    return doc

@app.get("/documents")
def get_documents():
    return list_documents()

@app.get("/documents/{doc_id}")
def get_document(doc_id: int):
    doc = get_document_by_id(doc_id)
    if doc is None:
        return {"error": "Document not found"}
    return doc

@app.delete("/documents/{doc_id}")
def delete_document(doc_id: int):
    deleted = delete_document_by_id(doc_id)
    if not deleted:
        return {"error": "Document not found"}
    return {"deleted": True, "id": doc_id}

@app.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    department: str = Form(...),
    role: str = Form(...),
):
    # Ensure storage folder exists
    storage_dir = Path("storage")
    storage_dir.mkdir(exist_ok=True)

    # Save file to backend/storage/
    safe_name = file.filename.replace("/", "_").replace("\\", "_")
    save_path = storage_dir / safe_name

    contents = await file.read()
    with open(save_path, "wb") as f:
        f.write(contents)

    # Store record in DB
    doc = add_uploaded_document(
        filename=file.filename,
        file_path=str(save_path),
        department=department,
        role=role,
    )
    return doc
