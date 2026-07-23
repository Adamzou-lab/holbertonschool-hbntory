"""Application FastAPI - Service IA HBntory.

Endpoints :
- POST /query   : pose une question a l'agent
- GET  /health  : readiness probe
- GET  /tools   : debug, liste des outils MCP exposes (gated par env)

Le lifespan gere :
- la connexion au serveur MCP (MCPToolset)
- la construction de l'agent PydanticAI
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from .agent import build_agent
from .config import get_settings
from .mcp_client import MCPConnection
from .schemas import (
    HealthResponse,
    QueryRequest,
    QueryResponse,
    ToolCallRecord,
    ToolsResponse,
    ToolSummary,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Cycle de vie de l'application.

    Demarrage : connexion au serveur MCP + construction de l'agent.
    Arret : fermeture propre de la connexion MCP.
    """
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    mcp = await MCPConnection.connect(settings)
    app.state.settings = settings
    app.state.mcp = mcp
    app.state.agent = build_agent(settings, mcp)

    logger.info(
        "HBntory AI Service ready on %s:%d (provider=%s, model=%s)",
        settings.ai_host,
        settings.ai_port,
        settings.llm_provider,
        settings.llm_model,
    )

    try:
        yield
    finally:
        await mcp.close()


app = FastAPI(
    title="HBntory AI Service",
    version="0.1.0",
    description="Service IA specialise inventaire pour HBntory. "
    "Utilise les outils MCP exposes par product_mcp_server.",
    lifespan=lifespan,
)

# CORS : le client web d'Adam est probablement sur un autre origine en dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# --- Endpoints ---


@app.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    s = request.app.state.settings
    return HealthResponse(
        status="ok",
        service="hbntory-ai-service",
        mcp_server_url=s.mcp_server_url,
        llm_provider=s.llm_provider,
        llm_model=s.llm_model,
    )


@app.get("/tools", response_model=ToolsResponse)
async def list_tools(request: Request) -> ToolsResponse:
    """Liste les outils MCP exposes (debug, gated par env)."""
    s = request.app.state.settings
    if not s.expose_tools_endpoint:
        raise HTTPException(status_code=404, detail="Not Found")

    mcp: MCPConnection = request.app.state.mcp
    names = await mcp.list_tool_names()
    # Le toolset ne fournit pas la description via get_tools() de maniere triviale
    # ; on agrege juste les noms ici. Les descriptions detaillees restent dans
    # le schema MCP que le client web peut fetch a part si besoin.
    return ToolsResponse(tools=[ToolSummary(name=n) for n in names])


@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest, request: Request) -> QueryResponse:
    """Pose une question a l'agent.

    L'agent utilise les outils MCP pour obtenir des donnees reelles et
    repond en langage naturel. La liste des outils appeles est exposee
    dans `tool_calls` pour l'observabilite / debug / demo.
    """
    agent = request.app.state.agent

    try:
        result = await agent.run(req.question)
    except Exception as exc:
        # On capture large : ca peut etre un erreur du LLM provider, du MCP,
        # ou un ModelRetry epuise.
        logger.exception("agent.run failed")
        raise HTTPException(
            status_code=503,
            detail="Inventory service temporarily unavailable.",
        ) from exc

    # Extraction des tool calls depuis les messages du run.
    tool_calls: list[ToolCallRecord] = []
    for msg in result.all_messages():
        # Les tool calls apparaissent dans les messages de l'assistant
        # sous forme de ModelRequest ; on les inspecte sans coupler au type exact.
        parts = getattr(msg, "parts", None)
        if not parts:
            continue
        for part in parts:
            part_type = getattr(part, "part_kind", "") or ""
            if "tool-call" in part_type:
                tool_name = getattr(part, "tool_name", None) or getattr(part, "tool_call_id", "unknown")
                tool_args = getattr(part, "args", None)
                # args peut etre un dict ou un objet ; on coerce en dict.
                if hasattr(tool_args, "model_dump"):
                    tool_args = tool_args.model_dump(exclude_none=True)
                elif not isinstance(tool_args, dict):
                    tool_args = None
                tool_calls.append(ToolCallRecord(tool=tool_name, args=tool_args))

    answer = result.output if isinstance(result.output, str) else str(result.output)
    return QueryResponse(answer=answer, tool_calls=tool_calls)


def main() -> None:
    """Lance uvicorn directement (utilise par le Dockerfile et le dev local)."""
    import uvicorn

    s = get_settings()
    uvicorn.run(
        "src.main:app",
        host=s.ai_host,
        port=s.ai_port,
        log_level=s.log_level.lower(),
        reload=False,
    )


if __name__ == "__main__":
    main()
