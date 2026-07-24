"""Application FastAPI - Service IA HBntory (Bloc 3 cote IA).

Architecture :
- 1 agent routeur (sortie structuree RoutingDecision)
- 4 agents specialises avec allowlists reelles
- 2 endpoints :
    * POST /query         : public, intents autorises = inventory / analytics / forecast
    * POST /internal/query : protege par X-Internal-Token, margin autorise en plus

Le lifespan gere la connexion au MCP (MCPToolset partage) et construit
tous les agents au demarrage.
"""

from __future__ import annotations

import logging
import re
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic_ai import Agent

from .agents import (
    build_analytics_agent,
    build_forecast_agent,
    build_inventory_agent,
    build_margin_agent,
    build_router_agent,
)
from .config import get_settings
from .mcp_client import MCPConnection
from .routing import Intent, RoutingDecision
from .schemas import (
    ErrorResponse,
    HealthResponse,
    QueryRequest,
    QueryResponse,
    ToolCallSummary,
    ToolsResponse,
    ToolSummary,
)
from .security import require_internal_token
from .toolsets import TOOLSETS, public_intents

logger = logging.getLogger(__name__)


# --- Regles deterministes (etape 1 du routage hybride) ---

_KEYWORD_RULES: list[tuple[str, Intent, str]] = [
    # Margin (tres specifique) : marge / rentabilite / rentable / cout d'achat / freight / depense / retirer
    (r"\bmarge[s]?\b|\brentabilit|\brentable[s]?\b|\bcout[s]?\s+(?:fournisseur|d'achat)|bfreight\b|\bachat[s]?\b|\bd[ée]pens|\bretirer\b",
     Intent.MARGIN, "mentions_margin"),
    # Forecast
    (r"\bpr[ée]vision|\btendance|\bsaisonni|\bstockout|\brupture[s]?\b|\bseuil\b|\bperiodicite\b|\bmouvement\b|\bdescendre\b|\breapprovisionn|\bestim",
     Intent.FORECAST, "mentions_forecast"),
    # Analytics (mots-cles specifiques aux classements/analyses)
    (r"\btop\b|\bdashboard|\bd[ée]ashboard|\br[ée]partition|\bagreg|\bcompar|\bclassement|\bchers?\b|\blourds?\b|\bsurrepr|\bfaible\b|\bfiable\b|\bcategorie\b|\bdiscontinued\b|\bcombien de\b|\banalyse[s]?\b",
     Intent.ANALYTICS, "mentions_analytics"),
    # Inventory (defaut — mots-cles generiques) — patterns en lowercase
    (r"\bstock\b|\bdisponibilit|\bbranche[s]?\b|\bd[ée]tail\b|\bproduit[s]?\b|\blyon\b|\bparis\b|\breste-t-il\b|\btrouver\b|\bdisponible\b",
     Intent.INVENTORY, "mentions_inventory"),
]


def deterministic_intent(question: str) -> RoutingDecision | None:
    """Tente une classification par mots-cles avant d'appeler le LLM."""
    q = question.lower()
    for pattern, intent, code in _KEYWORD_RULES:
        if re.search(pattern, q):
            return RoutingDecision(intent=intent, confidence=0.7, reason_code=code)
    return None


# --- Extraction des tool_calls depuis result.all_messages() ---


def _extract_tool_calls(result: Any) -> list[ToolCallSummary]:
    out: list[ToolCallSummary] = []
    try:
        messages = result.all_messages()
    except Exception:
        return out
    for msg in messages:
        parts = getattr(msg, "parts", None)
        if not parts:
            continue
        for part in parts:
            part_type = getattr(part, "part_kind", "") or ""
            if "tool-call" in part_type:
                tool_name = getattr(part, "tool_name", None) or "unknown"
                tool_args = getattr(part, "args", None)
                if hasattr(tool_args, "model_dump"):
                    tool_args = tool_args.model_dump(exclude_none=True)
                elif not isinstance(tool_args, dict):
                    tool_args = None
                out.append(ToolCallSummary(tool=tool_name, args=tool_args))
    return out


def _extract_limitations(result: Any) -> list[str]:
    """Tente de lire les limitations du run si exposes par l'agent."""
    out: list[str] = []
    try:
        messages = result.all_messages()
    except Exception:
        return out
    for msg in messages:
        text = getattr(msg, "content", None) or getattr(msg, "text", None)
        if isinstance(text, str) and "limit" in text.lower():
            out.append("agent signaled limitations in its reasoning")
    return out


# --- Lifespan ---


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    mcp = await MCPConnection.connect(settings)
    app.state.settings = settings
    app.state.mcp = mcp

    model_str = f"{settings.llm_provider}:{settings.llm_model}"
    mcp_toolset = mcp.toolset

    # Construction des 4 agents specialises
    agents: dict[str, Agent] = {
        "inventory": build_inventory_agent(model_str, mcp_toolset),
        "analytics": build_analytics_agent(model_str, mcp_toolset),
        "forecast": build_forecast_agent(model_str, mcp_toolset),
        "margin": build_margin_agent(model_str, mcp_toolset),
    }
    app.state.agents = agents
    app.state.router_agent = build_router_agent(model_str)

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
    version="0.2.0",
    description=(
        "Service IA HBntory multi-agent : Inventory, Analytics, Forecast, Margin. "
        "Endpoint public = /query (sans Margin). Endpoint interne = /internal/query (protege)."
    ),
    lifespan=lifespan,
)

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
    s = request.app.state.settings
    if not s.expose_tools_endpoint:
        raise HTTPException(status_code=404, detail="Not Found")
    mcp: MCPConnection = request.app.state.mcp
    names = await mcp.list_tool_names()
    return ToolsResponse(tools=[ToolSummary(name=n) for n in names])


# --- Dispatch ---


async def _route_and_dispatch(
    question: str,
    *,
    allowed_intents: list[str],
    request: Request,
) -> QueryResponse:
    request_id = uuid.uuid4().hex[:12]

    # 1. Regles deterministes
    decision = deterministic_intent(question)
    used_fallback = False
    if decision is None or decision.intent.value not in allowed_intents:
        # 2. Routeur LLM
        try:
            r = await request.app.state.router_agent.run(question)
            decision = r.output
        except Exception as exc:
            logger.exception("router_agent failed for request_id=%s", request_id)
            raise HTTPException(
                status_code=503,
                detail="Router temporarily unavailable.",
            ) from exc
        if decision.intent.value not in allowed_intents:
            used_fallback = True

    intent = decision.intent
    if intent == Intent.OUT_OF_SCOPE:
        return QueryResponse(
            answer=(
                "Je suis specialise dans l'inventaire HBntory et je ne peux pas repondre "
                "a cette question."
            ),
            intent=intent,
            routing_confidence=decision.confidence,
            tool_calls=[],
            data_origins=[],
            limitations=["out_of_scope"],
            request_id=request_id,
        )

    if used_fallback:
        # Cas ou le routeur a renvoye quelque chose hors de l'ensemble autorise
        # (ex: margin sur /query). On force le refus.
        if intent == Intent.MARGIN and "margin" not in allowed_intents:
            return QueryResponse(
                answer=(
                    "Les analyses de rentabilite sont reservees aux appels internes. "
                    "Cet endpoint public ne peut pas y acceder."
                ),
                intent=intent,
                routing_confidence=decision.confidence,
                tool_calls=[],
                data_origins=[],
                limitations=["margin_restricted_to_internal"],
                request_id=request_id,
            )
        # Sinon, fallback sur inventory (defaut raisonnable).
        intent = Intent.INVENTORY

    # 3. Dispatch vers l'agent specialise
    agent = request.app.state.agents[intent.value]
    try:
        result = await agent.run(question)
    except Exception as exc:
        logger.exception("agent %s failed request_id=%s", intent.value, request_id)
        raise HTTPException(
            status_code=503,
            detail=f"Agent {intent.value} temporarily unavailable.",
        ) from exc

    answer = result.output if isinstance(result.output, str) else str(result.output)
    tool_calls = _extract_tool_calls(result)
    limitations = _extract_limitations(result)

    data_origins: list[str] = []
    if intent == Intent.MARGIN:
        data_origins.append("synthetic_demo")

    return QueryResponse(
        answer=answer,
        intent=intent,
        routing_confidence=decision.confidence,
        tool_calls=tool_calls,
        data_origins=data_origins,
        limitations=limitations,
        request_id=request_id,
    )


@app.post(
    "/query",
    response_model=QueryResponse,
    responses={503: {"model": ErrorResponse}},
)
async def public_query(req: QueryRequest, request: Request) -> QueryResponse:
    """Endpoint public : intents autorises = inventory, analytics, forecast."""
    return await _route_and_dispatch(
        req.question, allowed_intents=public_intents(), request=request
    )


@app.post(
    "/internal/query",
    response_model=QueryResponse,
    responses={401: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def internal_query(
    req: QueryRequest,
    request: Request,
) -> QueryResponse:
    """Endpoint interne : tous les intents dont margin."""
    settings = request.app.state.settings
    require_internal_token(request, settings.internal_token)
    return await _route_and_dispatch(
        req.question,
        allowed_intents=list(TOOLSETS.keys()),
        request=request,
    )


def main() -> None:
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
