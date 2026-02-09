"""FastAPI ingestion API.

POST /api/ingest
- multipart/form-data with one or more "files" fields
- Saves files to a temp dir and runs ingestion_engine.ingest on that dir
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import List

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from ingestion_engine import ingest

app = FastAPI(title="Docspace Ingestion API", version="0.1")


@app.post("/api/ingest")
async def ingest_files(files: List[UploadFile] = File(...)) -> JSONResponse:
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

        try:
            ingest(
                source_path=temp_path,
                index_name=os.getenv("PINECONE_INDEX", ""),
                namespace=os.getenv("PINECONE_NAMESPACE"),
                chunk_size=int(os.getenv("INGEST_CHUNK_SIZE", "800")),
                overlap=int(os.getenv("INGEST_OVERLAP", "100")),
                batch_size=int(os.getenv("INGEST_BATCH_SIZE", "64")),
                embedding_model=os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
                cloud=os.getenv("PINECONE_CLOUD", "aws"),
                region=os.getenv("PINECONE_REGION", "us-east-1"),
                dry_run=os.getenv("INGEST_DRY_RUN", "false").lower() == "true",
            )
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return JSONResponse({"message": f"Ingestion started for {saved} file(s)."})


@app.get("/healthz")
def healthz() -> JSONResponse:
    return JSONResponse({"ok": True})
