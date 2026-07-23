"""Tests unitaires des outils produit (MCP tools).

Les tests utilisent httpx.MockTransport (voir conftest.py) pour
simuler les reponses de l'API Produit sans reseau.

Les outils sont appeles directement via la meme closure que celle
enregistree par register(). Pour eviter d'instancier FastMCP dans
les tests unitaires, on monkey-patch le client dans les fonctions
des tools en creant un mini-pipeline.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from src.product_client import ProductClient
from src.tools.product_tools import register as register_product_tools


def _make_mcp_with(client: ProductClient) -> FastMCP:
    mcp = FastMCP(name="test-mcp", stateless_http=True)
    register_product_tools(mcp, client)
    return mcp


def _tool(mcp: FastMCP, name: str):
    """Recupere la fonction interne d'un tool enregistre (pour test direct)."""
    tools = mcp._tool_manager._tools  # type: ignore[attr-defined]
    if name not in tools:
        raise KeyError(f"Tool {name} not registered")
    return tools[name].fn


# --- list_products ---


async def test_list_products_ok(product_ok_factory: ProductClient) -> None:
    mcp = _make_mcp_with(product_ok_factory)
    fn = _tool(mcp, "list_products")
    result: dict[str, Any] = await fn()
    assert "products" in result
    assert result["total"] == 3
    assert len(result["products"]) == 3


async def test_list_products_with_filters(product_ok_factory: ProductClient) -> None:
    """Les filtres sont passes tels quels a httpx (query string)."""
    seen_params: list[dict[str, str]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen_params.append(dict(req.url.params))
        return httpx.Response(200, json={"products": [], "total": 0, "limit": 5, "offset": 10})

    client = ProductClient(
        base_url="http://products.test",
        timeout_seconds=2.0,
        transport=httpx.MockTransport(handler),
    )

    mcp = _make_mcp_with(client)
    fn = _tool(mcp, "list_products")
    await fn(category="Accessories", limit=5, offset=10, include_discontinued=True)

    assert seen_params[0]["category"] == "Accessories"
    assert seen_params[0]["limit"] == "5"
    assert seen_params[0]["offset"] == "10"
    assert seen_params[0]["include_discontinued"] == "true"


async def test_list_products_schema_has_limit_constraint(product_ok_factory: ProductClient) -> None:
    """Verifie que le schema MCP genere inclut bien la contrainte 1..100 sur limit."""
    mcp = _make_mcp_with(product_ok_factory)
    tools = mcp._tool_manager._tools  # type: ignore[attr-defined]
    schema = tools["list_products"].parameters
    limit_schema = schema["properties"]["limit"]
    assert limit_schema.get("minimum") == 1
    assert limit_schema.get("maximum") == 100


async def test_list_products_500_maps_to_tool_error(product_500_factory: ProductClient) -> None:
    mcp = _make_mcp_with(product_500_factory)
    fn = _tool(mcp, "list_products")
    with pytest.raises(ToolError) as ei:
        await fn()
    assert "unavailable" in str(ei.value).lower()


# --- get_product ---


async def test_get_product_ok(product_ok_factory: ProductClient) -> None:
    mcp = _make_mcp_with(product_ok_factory)
    fn = _tool(mcp, "get_product")
    result: dict[str, Any] = await fn("HB-LAP-1001")
    assert result["sku"] == "HB-LAP-1001"
    assert result["id"] == 1


async def test_get_product_404(product_404_factory: ProductClient) -> None:
    mcp = _make_mcp_with(product_404_factory)
    fn = _tool(mcp, "get_product")
    with pytest.raises(ToolError) as ei:
        await fn("HB-FAUX-9999")
    assert "not found" in str(ei.value).lower()


async def test_get_product_500(product_500_factory: ProductClient) -> None:
    mcp = _make_mcp_with(product_500_factory)
    fn = _tool(mcp, "get_product")
    with pytest.raises(ToolError) as ei:
        await fn("1")
    assert "unavailable" in str(ei.value).lower()


# --- search_products ---


async def test_search_products_ok(product_ok_factory: ProductClient) -> None:
    mcp = _make_mcp_with(product_ok_factory)
    fn = _tool(mcp, "search_products")
    result: dict[str, Any] = await fn("laptop")
    assert "products" in result


async def test_search_products_schema_requires_non_empty_query(product_ok_factory: ProductClient) -> None:
    mcp = _make_mcp_with(product_ok_factory)
    tools = mcp._tool_manager._tools  # type: ignore[attr-defined]
    schema = tools["search_products"].parameters
    assert "query" in schema["required"]
    assert schema["properties"]["query"].get("minLength") == 1
