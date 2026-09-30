from __future__ import annotations

from pydantic import BaseModel, Field


class RAGSearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)


class RAGChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    session_id: str | None = Field(default=None, max_length=128)
