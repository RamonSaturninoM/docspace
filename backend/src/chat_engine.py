from __future__ import annotations

from typing import Any

try:
    from .ingestion_engine import answer_with_context
except ImportError:
    from ingestion_engine import answer_with_context


def chat_with_documents(message: str) -> dict[str, Any]:
    return answer_with_context(message)
