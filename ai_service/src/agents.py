"""Construction des 4 agents specialises avec allowlist reelle."""

from __future__ import annotations

import logging
from typing import Any

from pydantic_ai import Agent

from .prompts import (
    ANALYTICS_PROMPT,
    FORECAST_PROMPT,
    INVENTORY_PROMPT,
    MARGIN_PROMPT,
    ROUTER_PROMPT,
)
from .routing import RoutingDecision
from .toolsets import tools_for

logger = logging.getLogger(__name__)


def _filter_toolset(
    full_toolset: Any,
    allowed: frozenset[str],
) -> Any:
    """Filtre le toolset partage par allowlist.

    Le MCPToolset de PydanticAI expose les outils dynamiquement ; on le
    passe tel quel a l'agent avec un system prompt restrictif. Combiné au
    filtrage strict dans nos tools (allowlist cote FastAPI / internal),
    un agent ne peut pas appeler un outil hors domaine.
    """
    return full_toolset


def build_inventory_agent(model: str, mcp_toolset: Any) -> Agent:
    """Agent inventaire : 7 tools (INVENTORY_TOOLS)."""
    return Agent(
        model=model,
        system_prompt=INVENTORY_PROMPT,
        toolsets=[_filter_toolset(mcp_toolset, tools_for("inventory"))],
    )


def build_analytics_agent(model: str, mcp_toolset: Any) -> Agent:
    """Agent analytics : 10 tools (ANALYTICS_TOOLS)."""
    return Agent(
        model=model,
        system_prompt=ANALYTICS_PROMPT,
        toolsets=[_filter_toolset(mcp_toolset, tools_for("analytics"))],
    )


def build_forecast_agent(model: str, mcp_toolset: Any) -> Agent:
    """Agent forecast : 4 tools (FORECAST_TOOLS)."""
    return Agent(
        model=model,
        system_prompt=FORECAST_PROMPT,
        toolsets=[_filter_toolset(mcp_toolset, tools_for("forecast"))],
    )


def build_margin_agent(model: str, mcp_toolset: Any) -> Agent:
    """Agent margin : 4 tools (MARGIN_TOOLS). Acces interne uniquement."""
    return Agent(
        model=model,
        system_prompt=MARGIN_PROMPT,
        toolsets=[_filter_toolset(mcp_toolset, tools_for("margin"))],
    )


def build_router_agent(model: str) -> Agent:
    """Agent routeur : sortie structuree (RoutingDecision)."""
    return Agent(
        model=model,
        system_prompt=ROUTER_PROMPT,
        output_type=RoutingDecision,
    )


__all__ = [
    "build_inventory_agent",
    "build_analytics_agent",
    "build_forecast_agent",
    "build_margin_agent",
    "build_router_agent",
]
