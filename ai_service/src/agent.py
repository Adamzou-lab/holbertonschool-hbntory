"""Construction de l'agent PydanticAI specialise inventaire.

L'agent est :
- stateless (aucune memoire de conversation)
- mono-agent (pas d'orchestration multi-agent)
- branche sur les outils MCP fournis par mcp_client.MCPConnection

Le modele est configurable via env (LLM_PROVIDER, LLM_MODEL).
Le format attendu par PydanticAI est '<provider>:<model>' :
  - 'anthropic:claude-3-5-sonnet-latest'
  - 'openai:gpt-4o'
  - 'gemini:gemini-2.0-flash'
  - 'ollama:llama3.2'
"""

from __future__ import annotations

import logging

from pydantic_ai import Agent

from .config import Settings
from .mcp_client import MCPConnection
from .prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def build_agent(settings: Settings, mcp: MCPConnection) -> Agent:
    """Construit l'agent avec le toolset MCP deja connecte.

    L'agent est cree une seule fois au demarrage de l'app (dans le lifespan
    FastAPI). Pour chaque requete, on appelle agent.run(question) qui
    delegue au toolset MCP pour les tool calls.
    """
    model_str = f"{settings.llm_provider}:{settings.llm_model}"
    logger.info("Building PydanticAI agent with model=%s", model_str)
    return Agent(
        model=model_str,
        system_prompt=SYSTEM_PROMPT,
        toolsets=[mcp.toolset],
    )
