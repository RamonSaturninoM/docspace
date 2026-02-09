"""
Minimal ingestion engine for a documentation RAG app.

- Loads .md/.txt/.rst files from a path (file or directory)
- Splits into chunks with overlap
- Embeds using a low-cost local model (sentence-transformers)
- Upserts to Pinecone

Env vars:
- PINECONE_API_KEY (required)
- PINECONE_INDEX (required if --index not passed)
- PINECONE_CLOUD (default: aws)
- PINECONE_REGION (default: us-east-1)
- PINECONE_NAMESPACE (optional)
- EMBEDDING_MODEL (default: all-MiniLM-L6-v2)
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Dict, Tuple, Optional


SUPPORTED_EXTS = {".md", ".markdown", ".txt", ".rst"}


@dataclass
class Document:
    doc_id: str
    text: str
    metadata: Dict[str, str]


@dataclass
class Chunk:
    chunk_id: str
    text: str
    metadata: Dict[str, str]


class SentenceTransformersEmbeddings:
    def __init__(self, model_name: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "sentence-transformers is required. Install it with: pip install sentence-transformers"
            ) from exc

        self.model_name = model_name
        self.model = SentenceTransformer(model_name)

    @property
    def dimension(self) -> int:
        return self.model.get_sentence_embedding_dimension()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        # normalize_embeddings True helps cosine similarity
        return self.model.encode(texts, normalize_embeddings=True).tolist()


class PineconeWriter:
    def __init__(
        self,
        api_key: str,
        index_name: str,
        dimension: int,
        cloud: str,
        region: str,
    ) -> None:
        try:
            from pinecone import Pinecone, ServerlessSpec
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "pinecone is required. Install it with: pip install pinecone"
            ) from exc

        self.pc = Pinecone(api_key=api_key)
        self.index_name = index_name

        existing = {idx["name"] for idx in self.pc.list_indexes().get("indexes", [])}
        if index_name not in existing:
            self.pc.create_index(
                name=index_name,
                dimension=dimension,
                metric="cosine",
                spec=ServerlessSpec(cloud=cloud, region=region),
            )

        self.index = self.pc.Index(index_name)

    def upsert(self, vectors: List[Tuple[str, List[float], Dict[str, str]]], namespace: Optional[str]) -> None:
        if namespace:
            self.index.upsert(vectors=vectors, namespace=namespace)
        else:
            self.index.upsert(vectors=vectors)


def iter_files(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
        return

    for root, _, files in os.walk(path):
        for name in files:
            file_path = Path(root) / name
            if file_path.suffix.lower() in SUPPORTED_EXTS:
                yield file_path


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def load_documents(path: Path) -> List[Document]:
    docs: List[Document] = []
    for file_path in iter_files(path):
        text = read_text(file_path).strip()
        if not text:
            continue
        doc_id = hashlib.sha1(str(file_path).encode("utf-8")).hexdigest()
        metadata = {
            "source_path": str(file_path),
            "file_name": file_path.name,
        }
        docs.append(Document(doc_id=doc_id, text=text, metadata=metadata))
    return docs


def split_into_chunks(text: str, chunk_size: int, overlap: int) -> List[str]:
    words = text.split()
    if not words:
        return []
    if chunk_size <= 0:
        return [text]

    chunks: List[str] = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_words = words[start:end]
        chunks.append(" ".join(chunk_words))
        if end == len(words):
            break
        start = max(end - overlap, 0)
    return chunks


def chunk_documents(docs: List[Document], chunk_size: int, overlap: int) -> List[Chunk]:
    chunks: List[Chunk] = []
    for doc in docs:
        parts = split_into_chunks(doc.text, chunk_size=chunk_size, overlap=overlap)
        for i, part in enumerate(parts):
            chunk_id = f"{doc.doc_id}:{i}"
            metadata = dict(doc.metadata)
            metadata["chunk_index"] = str(i)
            metadata["doc_id"] = doc.doc_id
            chunks.append(Chunk(chunk_id=chunk_id, text=part, metadata=metadata))
    return chunks


def batch_iter(items: List[Chunk], batch_size: int) -> Iterable[List[Chunk]]:
    for i in range(0, len(items), batch_size):
        yield items[i : i + batch_size]


def ingest(
    source_path: Path,
    index_name: str,
    namespace: Optional[str],
    chunk_size: int,
    overlap: int,
    batch_size: int,
    embedding_model: str,
    cloud: str,
    region: str,
    dry_run: bool,
) -> None:
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key and not dry_run:
        raise RuntimeError("PINECONE_API_KEY is required (or use --dry-run).")

    docs = load_documents(source_path)
    if not docs:
        print("No documents found.")
        return

    chunks = chunk_documents(docs, chunk_size=chunk_size, overlap=overlap)
    print(f"Loaded {len(docs)} documents, {len(chunks)} chunks.")

    if dry_run:
        print("Dry run enabled; skipping embeddings and upsert.")
        return

    embedder = SentenceTransformersEmbeddings(embedding_model)
    writer = PineconeWriter(
        api_key=api_key,
        index_name=index_name,
        dimension=embedder.dimension,
        cloud=cloud,
        region=region,
    )

    for batch in batch_iter(chunks, batch_size):
        texts = [c.text for c in batch]
        vectors = embedder.embed_batch(texts)
        payload = [(c.chunk_id, vec, c.metadata) for c, vec in zip(batch, vectors)]
        writer.upsert(payload, namespace=namespace)

    print("Ingestion complete.")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest docs into Pinecone for RAG.")
    parser.add_argument("path", help="File or directory of docs to ingest")
    parser.add_argument("--index", default=os.getenv("PINECONE_INDEX"), help="Pinecone index name")
    parser.add_argument("--namespace", default=os.getenv("PINECONE_NAMESPACE"), help="Pinecone namespace")
    parser.add_argument("--chunk-size", type=int, default=800, help="Chunk size in words")
    parser.add_argument("--overlap", type=int, default=100, help="Chunk overlap in words")
    parser.add_argument("--batch-size", type=int, default=64, help="Embedding batch size")
    parser.add_argument(
        "--embedding-model",
        default=os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
        help="Sentence-transformers model name",
    )
    parser.add_argument("--cloud", default=os.getenv("PINECONE_CLOUD", "aws"), help="Pinecone cloud")
    parser.add_argument("--region", default=os.getenv("PINECONE_REGION", "us-east-1"), help="Pinecone region")
    parser.add_argument("--dry-run", action="store_true", help="Load + chunk only")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    if not args.index and not args.dry_run:
        print("Error: --index or PINECONE_INDEX is required.")
        sys.exit(2)

    ingest(
        source_path=Path(args.path),
        index_name=args.index,
        namespace=args.namespace,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
        batch_size=args.batch_size,
        embedding_model=args.embedding_model,
        cloud=args.cloud,
        region=args.region,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
