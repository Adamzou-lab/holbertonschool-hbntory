"""Modeles Pydantic pour les requetes et reponses de l'API REST."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .routing import Intent


class QueryRequest(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=2000,
        description="Question en langage naturel (1 a 2000 caracteres).",
    )


class ToolCallSummary(BaseModel):
    """Trace d'un appel d'outil par l'agent."""

    model_config = ConfigDict(extra="forbid")

    tool: str
    args: dict | None = None


class QueryResponse(BaseModel):
    """Reponse structuree de l'agent a une question."""

    model_config = ConfigDict(extra="forbid")

    answer: str
    intent: Intent
    routing_confidence: float = Field(ge=0, le=1)
    tool_calls: list[ToolCallSummary] = Field(default_factory=list)
    data_origins: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    request_id: str


class HealthResponse(BaseModel):
    status: str
    service: str
    mcp_server_url: str
    llm_provider: str
    llm_model: str


class ToolSummary(BaseModel):
    name: str
    description: str | None = None


class ToolsResponse(BaseModel):
    tools: list[ToolSummary]


class ErrorResponse(BaseModel):
    detail: str
    request_id: str | None = None
