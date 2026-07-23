"""Wrapper autour du MCPToolset de PydanticAI pour le serveur MCP HBntory.

Responsabilites :
- Construire un MCPToolset connecte au serveur MCP (transport Streamable HTTP).
- Gerer le cycle de vie (async context manager) dans le lifespan FastAPI.
- Permettre de lister les outils exposes (debug GET /tools).
- Permettre de verifier la disponibilite du serveur MCP (health check).

Le toolset est cree au demarrage de l'app et ferme a l'arret.
"""

from __future__ import annotations

import logging

from pydantic_ai.mcp import MCPToolset

from .config import Settings

logger = logging.getLogger(__name__)


class MCPConnection:
    """Encapsule un MCPToolset ouvert, expose par le lifespan FastAPI."""

    def __init__(self, toolset: MCPToolset) -> None:
        self._toolset = toolset

    @classmethod
    async def connect(cls, settings: Settings) -> MCPConnection:
        """Cree la connexion MCP au demarrage (context manager ouvert)."""
        logger.info("Connecting to MCP server at %s", settings.mcp_server_url)
        toolset = MCPToolset(settings.mcp_server_url)
        # On entre dans le context manager ici ; l'appelant doit appeler close().
        await toolset.__aenter__()
        logger.info("MCP server connected")
        return cls(toolset)

    @property
    def toolset(self) -> MCPToolset:
        return self._toolset

    async def close(self) -> None:
        """Ferme la connexion MCP."""
        logger.info("Closing MCP connection")
        try:
            await self._toolset.__aexit__(None, None, None)
        except Exception as exc:
            logger.warning("Error closing MCP toolset: %s", exc)

    async def list_tool_names(self) -> list[str]:
        """Liste les noms des outils exposes par le MCP (debug)."""
        try:
            tools = await self._toolset.get_tools()
            return list(tools.keys())
        except Exception as exc:
            logger.warning("Failed to list MCP tools: %s", exc)
            return []
