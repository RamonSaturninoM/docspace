from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import psycopg
    from psycopg.rows import dict_row
except ModuleNotFoundError:  # pragma: no cover
    psycopg = None
    dict_row = None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def file_kind(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in {".pdf"}:
        return "pdf"
    if suffix in {".doc", ".docx"}:
        return "doc"
    if suffix in {".xls", ".xlsx", ".csv"}:
        return "sheet"
    if suffix in {".ppt", ".pptx"}:
        return "slides"
    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        return "image"
    if suffix in {".txt", ".md"}:
        return "text"
    return "file"


def safe_filename(filename: str) -> str:
    cleaned = Path(filename).name.strip()
    return cleaned or f"upload-{uuid.uuid4().hex}"


@dataclass
class SavedFile:
    filename: str
    stored_name: str
    path: Path
    size_bytes: int
    mime_type: str | None


class FileStorage:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save_upload(self, filename: str, payload: bytes, mime_type: str | None) -> SavedFile:
        cleaned = safe_filename(filename)
        stored_name = f"{uuid.uuid4().hex}-{cleaned}"
        path = self.root / stored_name
        path.write_bytes(payload)
        return SavedFile(
            filename=cleaned,
            stored_name=stored_name,
            path=path,
            size_bytes=len(payload),
            mime_type=mime_type,
        )

    def delete(self, stored_name: str) -> None:
        path = self.root / stored_name
        if path.exists():
            path.unlink()

    def replace(self, previous_stored_name: str | None, saved_file: SavedFile) -> None:
        if previous_stored_name:
            self.delete(previous_stored_name)

    def public_path(self, stored_name: str) -> Path:
        return self.root / stored_name


class JsonDocumentStore:
    def __init__(self, data_path: Path, storage: FileStorage) -> None:
        self.data_path = data_path
        self.storage = storage
        self.lock = threading.Lock()
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.data_path.exists():
            self.data_path.write_text(
                json.dumps({"documents": [], "comments": [], "activity": []}, indent=2),
                encoding="utf-8",
            )

    def _load(self) -> dict[str, Any]:
        return json.loads(self.data_path.read_text(encoding="utf-8"))

    def _write(self, payload: dict[str, Any]) -> None:
        self.data_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _record_activity(self, payload: dict[str, Any], *, action: str, document_id: str, detail: str) -> None:
        payload["activity"].insert(
            0,
            {
                "id": uuid.uuid4().hex,
                "action": action,
                "document_id": document_id,
                "detail": detail,
                "created_at": isoformat(utc_now()),
            },
        )
        payload["activity"] = payload["activity"][:50]

    def list_documents(
        self,
        *,
        query: str = "",
        department: str | None = None,
        kind: str | None = None,
        pinned: bool | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        payload = self._load()
        items = payload["documents"]
        if query:
            lowered = query.lower()
            items = [
                item
                for item in items
                if lowered in item["title"].lower() or lowered in item["department"].lower()
            ]
        if department:
            items = [item for item in items if item["department"].lower() == department.lower()]
        if kind:
            items = [item for item in items if item["kind"] == kind]
        if pinned is not None:
            items = [item for item in items if item["pinned"] is pinned]
        items = sorted(items, key=lambda item: item["updated_at"], reverse=True)
        if limit is not None:
            items = items[:limit]
        return [self._document_with_comments(item, payload["comments"]) for item in items]

    def _document_with_comments(
        self, document: dict[str, Any], comments: list[dict[str, Any]]
    ) -> dict[str, Any]:
        item = dict(document)
        item["comments"] = [
            comment for comment in comments if comment["document_id"] == document["id"]
        ]
        item["download_url"] = f"/api/documents/{document['id']}/content"
        return item

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        payload = self._load()
        for item in payload["documents"]:
            if item["id"] == document_id:
                return self._document_with_comments(item, payload["comments"])
        return None

    def create_document(
        self,
        *,
        saved_file: SavedFile,
        title: str,
        department: str,
        owner: str,
        pinned: bool,
        description: str,
    ) -> dict[str, Any]:
        now = isoformat(utc_now())
        document = {
            "id": uuid.uuid4().hex,
            "title": title.strip() or saved_file.filename,
            "filename": saved_file.filename,
            "stored_name": saved_file.stored_name,
            "department": department.strip() or "General",
            "owner": owner.strip() or "Unknown",
            "description": description.strip(),
            "kind": file_kind(saved_file.filename),
            "mime_type": saved_file.mime_type or "application/octet-stream",
            "size_bytes": saved_file.size_bytes,
            "pinned": pinned,
            "created_at": now,
            "updated_at": now,
        }
        with self.lock:
            payload = self._load()
            payload["documents"].append(document)
            self._record_activity(
                payload,
                action="UPLOAD",
                document_id=document["id"],
                detail=f"Uploaded {document['title']}",
            )
            self._write(payload)
        return self.get_document(document["id"])  # type: ignore[return-value]

    def delete_document(self, document_id: str) -> bool:
        with self.lock:
            payload = self._load()
            for index, item in enumerate(payload["documents"]):
                if item["id"] != document_id:
                    continue
                self.storage.delete(item["stored_name"])
                deleted = payload["documents"].pop(index)
                payload["comments"] = [
                    comment for comment in payload["comments"] if comment["document_id"] != document_id
                ]
                self._record_activity(
                    payload,
                    action="DELETE",
                    document_id=document_id,
                    detail=f"Deleted {deleted['title']}",
                )
                self._write(payload)
                return True
        return False

    def set_pinned(self, document_id: str, pinned: bool) -> dict[str, Any] | None:
        with self.lock:
            payload = self._load()
            for item in payload["documents"]:
                if item["id"] != document_id:
                    continue
                item["pinned"] = pinned
                item["updated_at"] = isoformat(utc_now())
                self._record_activity(
                    payload,
                    action="PIN" if pinned else "UNPIN",
                    document_id=document_id,
                    detail=f"{'Pinned' if pinned else 'Unpinned'} {item['title']}",
                )
                self._write(payload)
                return self._document_with_comments(item, payload["comments"])
        return None

    def add_comment(self, document_id: str, author: str, body: str) -> dict[str, Any] | None:
        with self.lock:
            payload = self._load()
            document = next((item for item in payload["documents"] if item["id"] == document_id), None)
            if document is None:
                return None
            comment = {
                "id": uuid.uuid4().hex,
                "document_id": document_id,
                "author": author.strip() or "Anonymous",
                "body": body.strip(),
                "created_at": isoformat(utc_now()),
            }
            payload["comments"].append(comment)
            document["updated_at"] = isoformat(utc_now())
            self._record_activity(
                payload,
                action="COMMENT",
                document_id=document_id,
                detail=f"Commented on {document['title']}",
            )
            self._write(payload)
            return comment

    def dashboard_stats(self) -> dict[str, Any]:
        payload = self._load()
        documents = payload["documents"]
        activity = payload["activity"]
        return {
            "documents_total": len(documents),
            "pinned_total": sum(1 for item in documents if item["pinned"]),
            "comments_total": len(payload["comments"]),
            "storage_bytes": sum(item["size_bytes"] for item in documents),
            "recent_activity": activity[:10],
        }

    def file_path(self, document_id: str) -> Path | None:
        payload = self._load()
        for item in payload["documents"]:
            if item["id"] == document_id:
                path = self.storage.public_path(item["stored_name"])
                if path.exists():
                    return path
                return None
        return None


class PostgresDocumentStore:
    def __init__(self, dsn: str, storage: FileStorage) -> None:
        if psycopg is None:  # pragma: no cover
            raise RuntimeError("psycopg is required for Postgres storage.")
        self.dsn = dsn
        self.storage = storage
        self._init_db()

    def _connect(self):
        return psycopg.connect(self.dsn, row_factory=dict_row)

    def _init_db(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS documents (
                        id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        filename TEXT NOT NULL,
                        stored_name TEXT NOT NULL,
                        department TEXT NOT NULL,
                        owner_name TEXT NOT NULL,
                        description TEXT NOT NULL DEFAULT '',
                        kind TEXT NOT NULL,
                        mime_type TEXT NOT NULL,
                        size_bytes BIGINT NOT NULL,
                        pinned BOOLEAN NOT NULL DEFAULT FALSE,
                        created_at TIMESTAMPTZ NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS document_comments (
                        id TEXT PRIMARY KEY,
                        document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                        author TEXT NOT NULL,
                        body TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS document_activity (
                        id TEXT PRIMARY KEY,
                        action TEXT NOT NULL,
                        document_id TEXT NOT NULL,
                        detail TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
            conn.commit()

    def _record_activity(self, cur, *, action: str, document_id: str, detail: str) -> None:
        cur.execute(
            """
            INSERT INTO document_activity (id, action, document_id, detail, created_at)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (uuid.uuid4().hex, action, document_id, detail, utc_now()),
        )

    def _comments_map(self, conn) -> dict[str, list[dict[str, Any]]]:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, document_id, author, body, created_at
                FROM document_comments
                ORDER BY created_at ASC
                """
            )
            rows = cur.fetchall()
        mapping: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            row["created_at"] = isoformat(row["created_at"])
            mapping.setdefault(row["document_id"], []).append(row)
        return mapping

    def _document_payload(self, row: dict[str, Any], comments: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "title": row["title"],
            "filename": row["filename"],
            "stored_name": row["stored_name"],
            "department": row["department"],
            "owner": row["owner_name"],
            "description": row["description"],
            "kind": row["kind"],
            "mime_type": row["mime_type"],
            "size_bytes": row["size_bytes"],
            "pinned": row["pinned"],
            "created_at": isoformat(row["created_at"]),
            "updated_at": isoformat(row["updated_at"]),
            "comments": comments.get(row["id"], []),
            "download_url": f"/api/documents/{row['id']}/content",
        }

    def list_documents(
        self,
        *,
        query: str = "",
        department: str | None = None,
        kind: str | None = None,
        pinned: bool | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if query:
            clauses.append("(title ILIKE %s OR department ILIKE %s)")
            params.extend([f"%{query}%", f"%{query}%"])
        if department:
            clauses.append("department ILIKE %s")
            params.append(department)
        if kind:
            clauses.append("kind = %s")
            params.append(kind)
        if pinned is not None:
            clauses.append("pinned = %s")
            params.append(pinned)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        limit_sql = f"LIMIT {int(limit)}" if limit is not None else ""
        with self._connect() as conn:
            comments = self._comments_map(conn)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT *
                    FROM documents
                    {where}
                    ORDER BY updated_at DESC
                    {limit_sql}
                    """,
                    params,
                )
                rows = cur.fetchall()
        return [self._document_payload(row, comments) for row in rows]

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            comments = self._comments_map(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM documents WHERE id = %s", (document_id,))
                row = cur.fetchone()
        if row is None:
            return None
        return self._document_payload(row, comments)

    def create_document(
        self,
        *,
        saved_file: SavedFile,
        title: str,
        department: str,
        owner: str,
        pinned: bool,
        description: str,
    ) -> dict[str, Any]:
        document_id = uuid.uuid4().hex
        now = utc_now()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO documents (
                        id, title, filename, stored_name, department, owner_name, description,
                        kind, mime_type, size_bytes, pinned, created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        document_id,
                        title.strip() or saved_file.filename,
                        saved_file.filename,
                        saved_file.stored_name,
                        department.strip() or "General",
                        owner.strip() or "Unknown",
                        description.strip(),
                        file_kind(saved_file.filename),
                        saved_file.mime_type or "application/octet-stream",
                        saved_file.size_bytes,
                        pinned,
                        now,
                        now,
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO document_activity (id, action, document_id, detail, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (uuid.uuid4().hex, "UPLOAD", document_id, f"Uploaded {title or saved_file.filename}", now),
                )
            conn.commit()
        return self.get_document(document_id)  # type: ignore[return-value]

    def delete_document(self, document_id: str) -> bool:
        document = self.get_document(document_id)
        if document is None:
            return False
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM documents WHERE id = %s", (document_id,))
                self._record_activity(
                    cur,
                    action="DELETE",
                    document_id=document_id,
                    detail=f"Deleted {document['title']}",
                )
            conn.commit()
        self.storage.delete(document["stored_name"])
        return True

    def set_pinned(self, document_id: str, pinned: bool) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE documents SET pinned = %s, updated_at = %s WHERE id = %s RETURNING *",
                    (pinned, utc_now(), document_id),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                self._record_activity(
                    cur,
                    action="PIN" if pinned else "UNPIN",
                    document_id=document_id,
                    detail=f"{'Pinned' if pinned else 'Unpinned'} {row['title']}",
                )
            conn.commit()
        return self.get_document(document_id)

    def add_comment(self, document_id: str, author: str, body: str) -> dict[str, Any] | None:
        if self.get_document(document_id) is None:
            return None
        comment = {
            "id": uuid.uuid4().hex,
            "document_id": document_id,
            "author": author.strip() or "Anonymous",
            "body": body.strip(),
            "created_at": utc_now(),
        }
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO document_comments (id, document_id, author, body, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        comment["id"],
                        comment["document_id"],
                        comment["author"],
                        comment["body"],
                        comment["created_at"],
                    ),
                )
                cur.execute(
                    "UPDATE documents SET updated_at = %s WHERE id = %s",
                    (utc_now(), document_id),
                )
                self._record_activity(
                    cur,
                    action="COMMENT",
                    document_id=document_id,
                    detail="Added a comment",
                )
            conn.commit()
        comment["created_at"] = isoformat(comment["created_at"])
        return comment

    def dashboard_stats(self) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        COUNT(*) AS documents_total,
                        COUNT(*) FILTER (WHERE pinned) AS pinned_total,
                        COALESCE(SUM(size_bytes), 0) AS storage_bytes
                    FROM documents
                    """
                )
                stats = cur.fetchone()
                cur.execute("SELECT COUNT(*) AS comments_total FROM document_comments")
                comments = cur.fetchone()
                cur.execute(
                    """
                    SELECT id, action, document_id, detail, created_at
                    FROM document_activity
                    ORDER BY created_at DESC
                    LIMIT 10
                    """
                )
                activity = cur.fetchall()
        return {
            "documents_total": stats["documents_total"],
            "pinned_total": stats["pinned_total"],
            "comments_total": comments["comments_total"],
            "storage_bytes": stats["storage_bytes"],
            "recent_activity": [
                {**row, "created_at": isoformat(row["created_at"])} for row in activity
            ],
        }

    def file_path(self, document_id: str) -> Path | None:
        document = self.get_document(document_id)
        if document is None:
            return None
        path = self.storage.public_path(document["stored_name"])
        return path if path.exists() else None


def build_document_store(base_dir: Path):
    storage = FileStorage(base_dir / "storage" / "uploads")
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url and psycopg is not None:
        return PostgresDocumentStore(database_url, storage)
    return JsonDocumentStore(base_dir / "storage" / "documents.json", storage)
