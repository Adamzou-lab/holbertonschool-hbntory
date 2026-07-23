"""Test d'integration bout-en-bout : AI service + MCP server (en memoire).

Ce test importe le vrai build_server() du Bloc 2 et le branche sur un
Agent PydanticAI reellement execute (avec TestModel, pas de cle API reelle).

Objectif : prouver que le Service IA est correctement cable au serveur MCP
Bloc 2 -- la stack complete (PydanticAI -> MCPToolset -> FastMCP -> tools
personnalises) fonctionne. Les outils echoueront (l'API Produit n'est pas
lancee dans cet env de test), mais on verifie qu'ils sont *appeles*, ce qui
est l'integrateur reel entre les deux services.

Skip automatique si le package product_mcp_server n'est pas importable
(PYTHONPATH ou installation cote tests).
"""

from __future__ import annotations

import pytest

pydantic_ai = pytest.importorskip("pydantic_ai")
fastmcp = pytest.importorskip("fastmcp")

# Import conditionnel du Bloc 2 : si pas dans le PYTHONPATH, on skip.
try:
    from product_mcp_server.src.server import (
        build_server as build_mcp_server,  # type: ignore[import-not-found]
    )
except ImportError:
    build_mcp_server = None  # type: ignore[assignment]

pytestmark = pytest.mark.skipif(
    build_mcp_server is None,
    reason="product_mcp_server pas dans le PYTHONPATH (integration test)",
)


async def test_mcp_server_builds_in_process() -> None:
    """Le serveur MCP (Bloc 2) demarre en memoire sans I/O."""
    mcp = build_mcp_server()
    assert mcp is not None
    # Le toolset a 7 outils (3 produit + 4 stock).
    assert len(mcp._tool_manager._tools) == 7  # type: ignore[attr-defined]


async def test_ai_service_can_call_mcp_tools_via_in_process_fastmcp() -> None:
    """Integration reelle : AI Agent -> MCPToolset -> FastMCP en memoire.

    On verifie que l'agent appelle au moins un outil du MCP. On accepte
    l'echec final (ToolError sur la connexion API Produit reelle) puisque
    l'environnement de test n'a pas de Docker -- ce qu'on cherche a prouver
    c'est le *cablage*, pas le resultat fonctionnel.
    """
    from ai_service.src.prompts import SYSTEM_PROMPT
    from fastmcp import Client
    from pydantic_ai import Agent
    from pydantic_ai.exceptions import UnexpectedModelBehavior
    from pydantic_ai.mcp import MCPToolset
    from pydantic_ai.models.test import TestModel

    mcp_server = build_mcp_server()
    client = Client(mcp_server)
    toolset = MCPToolset(client)

    agent = Agent(
        model=TestModel(),
        toolsets=[toolset],
        system_prompt=SYSTEM_PROMPT,
    )

    async with toolset:
        with pytest.raises(UnexpectedModelBehavior) as excinfo:
            await agent.run("Donne-moi les details de HB-LAP-1001")

        msg = str(excinfo.value)
        assert any(
            tool in msg
            for tool in [
                "get_product",
                "list_products",
                "search_products",
                "list_branches",
                "get_product_availability",
                "get_branch_inventory",
                "check_shopping_list",
            ]
        ), f"Expected MCP tool name in error, got: {msg[:200]}"


async def test_mcpconnection_wrapper_works() -> None:
    """Le wrapper MCPConnection (utilise dans le lifespan FastAPI) instancie
    correctement un MCPToolset et peut lister les outils."""
    from fastmcp import Client
    from pydantic_ai.mcp import MCPToolset

    mcp_server = build_mcp_server()
    client = Client(mcp_server)
    toolset = MCPToolset(client)

    async with toolset:
        # list_tools() renvoie la liste des outils declares cote serveur MCP.
        tools_list = await toolset.list_tools()
        names = {t.name for t in tools_list}
        assert "list_products" in names
        assert "get_product" in names
        assert "search_products" in names
        assert "list_branches" in names
        assert "get_product_availability" in names
        assert "get_branch_inventory" in names
        assert "check_shopping_list" in names
        assert len(names) == 7
