from __future__ import annotations

import json
import os
import re
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib import error, request


OPENAI_API_URL = "https://api.openai.com/v1"
PINECONE_CONTROL_URL = "https://api.pinecone.io"
PINECONE_API_VERSION = os.getenv("PINECONE_API_VERSION", "2025-10")


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        stripped = data.strip()
        if stripped:
            self.parts.append(stripped)

    def text(self) -> str:
        return "\n".join(self.parts)


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP error {exc.code} for {url}: {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Connection error for {url}: {exc.reason}") from exc


def _get_json(url: str, headers: dict[str, str]) -> dict[str, Any]:
    req = request.Request(url, headers=headers, method="GET")
    try:
        with request.urlopen(req, timeout=45) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP error {exc.code} for {url}: {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Connection error for {url}: {exc.reason}") from exc


def _delete_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=45) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP error {exc.code} for {url}: {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Connection error for {url}: {exc.reason}") from exc


def normalize_text(value: str) -> str:
    cleaned = value.replace("\x00", " ")
    cleaned = re.sub(r"\r\n?", "\n", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def is_small_talk(message: str) -> bool:
    lowered = message.strip().lower()
    patterns = {
        "thanks",
        "thank you",
        "thx",
        "txs",
        "ok thanks",
        "okay thanks",
        "ok txs",
        "cool thanks",
        "got it",
        "hello",
        "hi",
        "hey",
        "bye",
    }
    return lowered in patterns


def extract_docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        with archive.open("word/document.xml") as handle:
            xml_text = handle.read().decode("utf-8", errors="ignore")
    return normalize_text(re.sub(r"<[^>]+>", " ", xml_text))


def extract_html_text(path: Path) -> str:
    parser = TextExtractor()
    parser.feed(path.read_text(encoding="utf-8", errors="ignore"))
    return normalize_text(parser.text())


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".csv", ".json"}:
        return normalize_text(path.read_text(encoding="utf-8", errors="ignore"))
    if suffix in {".html", ".htm"}:
        return extract_html_text(path)
    if suffix == ".docx":
        return extract_docx_text(path)
    if suffix == ".pdf":
        raise RuntimeError("PDF indexing is not configured in this environment yet.")
    return normalize_text(path.read_text(encoding="utf-8", errors="ignore"))


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def openai_headers() -> dict[str, str]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY in .env.")
    return {"Authorization": f"Bearer {api_key}"}


def create_embeddings(texts: list[str]) -> list[list[float]]:
    model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small").strip()
    payload = _post_json(
        f"{OPENAI_API_URL}/embeddings",
        {"model": model, "input": texts},
        openai_headers(),
    )
    return [item["embedding"] for item in payload["data"]]


def chat_completion(messages: list[dict[str, str]]) -> str:
    model = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini").strip()
    payload = _post_json(
        f"{OPENAI_API_URL}/chat/completions",
        {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
            "max_completion_tokens": 700,
        },
        openai_headers(),
    )
    return payload["choices"][0]["message"]["content"].strip()


def pinecone_headers() -> dict[str, str]:
    api_key = os.getenv("PINECONE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing PINECONE_API_KEY in .env.")
    return {
        "Api-Key": api_key,
        "X-Pinecone-Api-Version": PINECONE_API_VERSION,
        "Accept": "application/json",
    }


def pinecone_host() -> str:
    direct = os.getenv("PINECONE_HOST", "").strip()
    if direct:
        return direct.replace("https://", "")

    index_name = os.getenv("PINECONE_INDEX", "").strip()
    if not index_name:
        raise RuntimeError("Missing PINECONE_INDEX or PINECONE_HOST in .env.")

    payload = _get_json(f"{PINECONE_CONTROL_URL}/indexes/{index_name}", pinecone_headers())
    host = payload.get("host", "").strip()
    if not host:
        raise RuntimeError("Pinecone index host was not returned by describe index.")
    return host


def pinecone_namespace() -> str:
    return os.getenv("PINECONE_NAMESPACE", "").strip()


def upsert_chunks(document: dict[str, Any], chunks: list[str]) -> int:
    host = pinecone_host()
    embeddings = create_embeddings(chunks)
    vectors = []
    for index, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=False)):
        vectors.append(
            {
                "id": f"{document['id']}:{index}",
                "values": embedding,
                "metadata": {
                    "document_id": document["id"],
                    "title": document["title"],
                    "department": document["department"],
                    "owner": document["owner"],
                    "chunk_index": index,
                    "text": chunk,
                },
            }
        )
    _post_json(
        f"https://{host}/vectors/upsert",
        {"vectors": vectors, "namespace": pinecone_namespace()},
        pinecone_headers(),
    )
    return len(vectors)


def delete_document_vectors(document_id: str) -> None:
    host = pinecone_host()
    _delete_json(
        f"https://{host}/vectors/delete",
        {
            "namespace": pinecone_namespace(),
            "filter": {"document_id": {"$eq": document_id}},
        },
        pinecone_headers(),
    )


def query_chunks(message: str, top_k: int = 6) -> list[dict[str, Any]]:
    host = pinecone_host()
    embedding = create_embeddings([message])[0]
    payload = _post_json(
        f"https://{host}/query",
        {
            "vector": embedding,
            "topK": top_k,
            "includeMetadata": True,
            "namespace": pinecone_namespace(),
        },
        pinecone_headers(),
    )
    return payload.get("matches", [])


def answer_with_context(message: str, top_k: int = 6) -> dict[str, Any]:
    if is_small_talk(message):
        reply = chat_completion(
            [
                {
                    "role": "system",
                    "content": "You are a concise, polite assistant. Reply naturally to conversational messages.",
                },
                {"role": "user", "content": message},
            ]
        )
        return {"reply": reply, "sources": []}

    matches = query_chunks(message, top_k=top_k)
    min_score = float(os.getenv("RAG_MIN_SCORE", "0.55"))
    usable = [
        match
        for match in matches
        if match.get("metadata", {}).get("text") and float(match.get("score", 0.0)) >= min_score
    ]
    if not usable:
        reply = chat_completion(
            [
                {
                    "role": "system",
                    "content": (
                        "You are a concise assistant. If the message is general conversation, reply naturally. "
                        "If it is asking about documents or company facts you do not have, say you could not find that in the indexed documents."
                    ),
                },
                {"role": "user", "content": message},
            ]
        )
        return {"reply": reply, "sources": []}

    context_blocks = []
    sources = []
    seen: set[str] = set()
    for match in usable:
        metadata = match["metadata"]
        context_blocks.append(
            f"[{metadata['title']} - chunk {metadata.get('chunk_index', 0)}]\n{metadata['text']}"
        )
        source_key = metadata["document_id"]
        if source_key not in seen:
            seen.add(source_key)
            sources.append(
                {
                    "document_id": metadata["document_id"],
                    "title": metadata["title"],
                    "department": metadata.get("department", ""),
                }
            )

    prompt = (
        "Answer the question using only the document context below. "
        "If the context is insufficient, say that clearly. "
        "At the end, mention the document titles you used in a short 'Sources:' line.\n\n"
        f"Context:\n{'\n\n'.join(context_blocks)}"
    )
    reply = chat_completion(
        [
            {
                "role": "system",
                "content": "You are a document assistant. Stay grounded in the retrieved context.",
            },
            {"role": "user", "content": f"{prompt}\n\nQuestion: {message}"},
        ]
    )
    return {"reply": reply, "sources": sources}


def index_document_file(document: dict[str, Any], file_path: Path) -> dict[str, Any]:
    text = extract_text(file_path)
    if not text:
        raise RuntimeError("No indexable text could be extracted from the file.")
    chunk_size = int(os.getenv("INGEST_CHUNK_SIZE", "1200"))
    overlap = int(os.getenv("INGEST_OVERLAP", "200"))
    chunks = chunk_text(text, chunk_size, overlap)
    count = upsert_chunks(document, chunks)
    return {"chunk_count": count}
