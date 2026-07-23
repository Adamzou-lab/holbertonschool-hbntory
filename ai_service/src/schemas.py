"""Modeles Pydantic pour les requetes et reponses de l'API REST."""

from __future__ import annotations

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Question utilisateur envoyee a l'agent."""

    question: str = Field(
        min_length=1,
        max_length=2000,
        description="Question en langage naturel (1 a 2000 caracteres).",
    )


class ToolCallRecord(BaseModel):
    """Trace d'un appel d'outil par l'agent (debug + observabilite)."""

    tool: str = Field(description="Nom de l'outil MCP appele.")
    args: dict | None = Field(default=None, description="Arguments passes a l'outil.")


class QueryResponse(BaseModel):
    """Reponse de l'agent a une question."""

    answer: str = Field(description="Reponse en langage naturel de l'agent.")
    tool_calls: list[ToolCallRecord] = Field(
        default_factory=list,
        description="Liste des outils MCP appeles pour produire la reponse (debug).",
    )


class HealthResponse(BaseModel):
    """Reponse de /health."""

    status: str
    service: str
    mcp_server_url: str
    llm_provider: str
    llm_model: str


class ToolSummary(BaseModel):
    """Resume d'un outil expose par le MCP."""

    name: str
    description: str | None = None


class ToolsResponse(BaseModel):
    """Reponse de /tools (debug)."""

    tools: list[ToolSummary]
