"""Test d'integration bout-en-bout : AI service + MCP server (en memoire).

Skip automatique si product_mcp_server n'est pas dans le PYTHONPATH.
"""

from __future__ import annotations

import pytest

fastmcp = pytest.importorskip("fastmcp")

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
    tools = mcp._tool_manager._tools  # type: ignore[attr-defined]
    assert len(tools) == 25


async def test_ai_service_can_call_mcp_tools_via_in_process_fastmcp() -> None:
    """Integration reelle : AI Agent -> MCPToolset -> FastMCP en memoire."""
    from ai_service.src.prompts import INVENTORY_PROMPT
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
        system_prompt=INVENTORY_PROMPT,
    )

    async with toolset:
        with pytest.raises(UnexpectedModelBehavior) as excinfo:
            await agent.run("Donne-moi les details de HB-LAP-1001")
        msg = str(excinfo.value)
        assert any(
            tool in msg
            for tool in [
                "get_product", "list_products", "search_products",
                "list_branches", "get_product_availability",
                "get_branch_inventory", "check_shopping_list",
            ]
        ), f"Expected MCP tool name in error, got: {msg[:200]}"


async def test_all_25_tools_documented() -> None:
    """Le MCP expose les 25 outils attendus (3 + 4 + 10 + 4 + 4)."""
    mcp = build_mcp_server()
    tools = mcp._tool_manager._tools  # type: ignore[attr-defined]
    expected = {
        # produit
        "list_products", "get_product", "search_products",
        # stock
        "list_branches", "get_product_availability",
        "get_branch_inventory", "check_shopping_list",
        # analytics (10)
        "analyze_catalog_by_category", "find_extreme_prices", "find_extreme_weights",
        "analyze_supplier_portfolio", "estimate_catalog_stock_value",
        "assess_storage_complexity", "find_discontinued_with_stock",
        "analyze_stock_distribution", "find_overstocked_products",
        "find_understocked_products",
        # forecast (4)
        "get_stock_history", "analyze_stock_trend",
        "forecast_stockout_and_reorder", "detect_seasonal_pattern",
        # margin (4)
        "compute_product_margin", "identify_most_profitable",
        "compute_supplier_cost", "analyze_storage_efficiency",
    }
    assert set(tools.keys()) == expected
