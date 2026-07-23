"""Tests unitaires des outils stock (MCP tools).

Les tests utilisent httpx.MockTransport pour simuler les reponses
de l'API interne du Backoffice. Tant que Nico n'a pas livre les
routes /api/internal/..., ces tests servent de contrat :
le MCP respecte la forme de la reponse specifiee dans le plan.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from src.product_client import ProductClient
from src.resolvers import clear_sku_cache
from src.stock_client import StockClient
from src.tools.stock_tools import register as register_stock_tools


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    clear_sku_cache()


def _make_mcp(
    *,
    product_handler: Any | None = None,
    stock_handler: Any | None = None,
) -> tuple[FastMCP, ProductClient, StockClient]:
    """Construit un FastMCP avec des clients httpx pilotes par mock."""

    if product_handler is None:
        def product_handler(req: httpx.Request) -> httpx.Response:
            sku = req.url.path.rsplit("/", 1)[-1]
            return httpx.Response(200, json={"id": 1, "sku": sku, "name": f"Product {sku}"})

    product_client = ProductClient(
        base_url="http://products.test",
        timeout_seconds=2.0,
        transport=httpx.MockTransport(product_handler),
    )

    if stock_handler is None:
        def stock_handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[])

    stock_client = StockClient(
        base_url="http://backoffice.test",
        internal_token="test-token",
        timeout_seconds=2.0,
        transport=httpx.MockTransport(stock_handler),
    )

    mcp = FastMCP(name="test-mcp-stock", stateless_http=True)
    register_stock_tools(mcp, stock_client, product_client)
    return mcp, product_client, stock_client


def _tool(mcp: FastMCP, name: str):
    tools = mcp._tool_manager._tools  # type: ignore[attr-defined]
    if name not in tools:
        raise KeyError(f"Tool {name} not registered")
    return tools[name].fn


# --- list_branches ---


async def test_list_branches_ok() -> None:
    branches = [
        {"id": 1, "name": "Paris"},
        {"id": 2, "name": "Lyon"},
    ]

    def stock_handler(req: httpx.Request) -> httpx.Response:
        assert req.headers.get("X-Internal-Token") == "test-token"
        return httpx.Response(200, json=branches)

    mcp, _, _ = _make_mcp(stock_handler=stock_handler)
    fn = _tool(mcp, "list_branches")
    result = await fn()
    assert result == {"branches": branches}


async def test_list_branches_403_maps_to_tool_error() -> None:
    def stock_handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "forbidden"})

    mcp, _, _ = _make_mcp(stock_handler=stock_handler)
    fn = _tool(mcp, "list_branches")
    with pytest.raises(ToolError) as ei:
        await fn()
    assert "denied" in str(ei.value).lower()


# --- get_product_availability ---


async def test_get_product_availability_numeric_id() -> None:
    rows = [
        {"branch_id": 1, "branch_name": "Paris", "quantity": 50},
        {"branch_id": 2, "branch_name": "Lyon", "quantity": 5},
    ]

    def stock_handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/internal/stock/by-product/1"
        return httpx.Response(200, json=rows)

    mcp, _, _ = _make_mcp(stock_handler=stock_handler)
    fn = _tool(mcp, "get_product_availability")
    result = await fn("1")
    assert result == {"product_id": 1, "branches": rows, "total": 55}


async def test_get_product_availability_sku_resolved() -> None:
    """Le SKU est resolu via le product_client, puis on appelle le stock avec l'id."""
    stock_calls: list[str] = []

    def stock_handler(req: httpx.Request) -> httpx.Response:
        stock_calls.append(req.url.path)
        return httpx.Response(200, json=[{"branch_id": 1, "branch_name": "Paris", "quantity": 12}])

    mcp, _, _ = _make_mcp(stock_handler=stock_handler)
    fn = _tool(mcp, "get_product_availability")
    result = await fn("HB-LAP-1001")
    assert result["product_id"] == 1
    assert stock_calls == ["/api/internal/stock/by-product/1"]


async def test_get_product_availability_no_stock_empty_list() -> None:
    def stock_handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    mcp, _, _ = _make_mcp(stock_handler=stock_handler)
    fn = _tool(mcp, "get_product_availability")
    result = await fn("1")
    assert result == {"product_id": 1, "branches": [], "total": 0}


async def test_get_product_availability_invalid_id() -> None:
    mcp, _, _ = _make_mcp()
    fn = _tool(mcp, "get_product_availability")
    with pytest.raises(ToolError):
        await fn("foo-bar")


# --- get_branch_inventory ---


async def test_get_branch_inventory_ok() -> None:
    rows = [
        {"product_id": 1, "quantity": 50},
        {"product_id": 2, "quantity": 10},
    ]

    def stock_handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/internal/stock/by-branch/1"
        return httpx.Response(200, json=rows)

    mcp, _, _ = _make_mcp(stock_handler=stock_handler)
    fn = _tool(mcp, "get_branch_inventory")
    result = await fn(branch_id=1)
    assert result == {"branch_id": 1, "items": rows, "total_items": 2}


async def test_get_branch_inventory_404_maps_to_tool_error() -> None:
    def stock_handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "branch not found"})

    mcp, _, _ = _make_mcp(stock_handler=stock_handler)
    fn = _tool(mcp, "get_branch_inventory")
    with pytest.raises(ToolError) as ei:
        await fn(branch_id=999)
    assert "not found" in str(ei.value).lower()


async def test_get_branch_inventory_invalid_branch_id() -> None:
    mcp, _, _ = _make_mcp()
    fn = _tool(mcp, "get_branch_inventory")
    with pytest.raises(ToolError):
        await fn(branch_id=0)


# --- check_shopping_list ---


async def test_check_shopping_list_full_satisfaction_single_branch() -> None:
    """Une seule branche satisfait toute la liste."""
    items_sent_to_backoffice: list[Any] = []
    payload = {
        "branches": [
            {
                "branch_id": 1,
                "branch_name": "Paris",
                "items": [
                    {"product_id": 1, "requested": 3, "available": 50, "satisfied": True},
                    {"product_id": 2, "requested": 2, "available": 10, "satisfied": True},
                ],
                "missing": [],
                "recommendation": "Paris satisfait 100% de la liste.",
            }
        ],
        "strategy": "single",
        "recommendation": "Visitez Paris.",
    }

    def stock_handler(req: httpx.Request) -> httpx.Response:
        import json
        body = json.loads(req.content)
        items_sent_to_backoffice.append(body)
        return httpx.Response(200, json=payload)

    mcp, _, _ = _make_mcp(stock_handler=stock_handler)
    fn = _tool(mcp, "check_shopping_list")
    result = await fn(items=[{"product_id": "1", "quantity": 3}, {"product_id": "2", "quantity": 2}])
    assert result == payload
    # Les product_id doivent etre resolus en int avant d'etre envoyes au Backoffice
    assert items_sent_to_backoffice[0]["items"] == [
        {"product_id": 1, "quantity": 3},
        {"product_id": 2, "quantity": 2},
    ]


async def test_check_shopping_list_partial_satisfaction_multiple_branches() -> None:
    """Deux branches, satisfaction partielle cote chacune."""
    payload = {
        "branches": [
            {
                "branch_id": 1,
                "branch_name": "Paris",
                "items": [
                    {"product_id": 1, "requested": 5, "available": 10, "satisfied": True},
                    {"product_id": 2, "requested": 3, "available": 0, "satisfied": False},
                ],
                "missing": [{"product_id": 2, "short": 3}],
                "recommendation": "Paris a 1 produit sur 2.",
            },
            {
                "branch_id": 2,
                "branch_name": "Lyon",
                "items": [
                    {"product_id": 1, "requested": 5, "available": 0, "satisfied": False},
                    {"product_id": 2, "requested": 3, "available": 4, "satisfied": True},
                ],
                "missing": [{"product_id": 1, "short": 5}],
                "recommendation": "Lyon a 1 produit sur 2.",
            },
        ],
        "strategy": "split",
        "recommendation": "Aucune branche ne couvre tout, combinez Paris et Lyon.",
    }

    def stock_handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    mcp, _, _ = _make_mcp(stock_handler=stock_handler)
    fn = _tool(mcp, "check_shopping_list")
    result = await fn(items=[{"product_id": "1", "quantity": 5}, {"product_id": "2", "quantity": 3}])
    assert result["strategy"] == "split"
    assert len(result["branches"]) == 2


async def test_check_shopping_list_rejects_invalid_quantity() -> None:
    mcp, _, _ = _make_mcp()
    fn = _tool(mcp, "check_shopping_list")
    with pytest.raises(ToolError) as ei:
        await fn(items=[{"product_id": "1", "quantity": 0}])
    assert "positive" in str(ei.value).lower()


async def test_check_shopping_list_rejects_missing_product_id() -> None:
    mcp, _, _ = _make_mcp()
    fn = _tool(mcp, "check_shopping_list")
    with pytest.raises(ToolError):
        await fn(items=[{"quantity": 1}])


async def test_check_shopping_list_rejects_empty_items() -> None:
    """Le tool lui-meme refuse une liste vide -> ToolError."""
    mcp, _, _ = _make_mcp()
    fn = _tool(mcp, "check_shopping_list")
    with pytest.raises(ToolError):
        await fn(items=[])


async def test_check_shopping_list_500_maps_to_tool_error() -> None:
    def stock_handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "server"})

    mcp, _, _ = _make_mcp(stock_handler=stock_handler)
    fn = _tool(mcp, "check_shopping_list")
    with pytest.raises(ToolError) as ei:
        await fn(items=[{"product_id": "1", "quantity": 1}])
    assert "unreachable" in str(ei.value).lower()


# --- Auth header sur tous les appels ---


async def test_all_stock_calls_send_internal_token() -> None:
    """Tous les appels au Backoffice portent X-Internal-Token."""
    seen_tokens: list[str | None] = []

    def stock_handler(req: httpx.Request) -> httpx.Response:
        seen_tokens.append(req.headers.get("X-Internal-Token"))
        if req.url.path == "/api/internal/branches":
            return httpx.Response(200, json=[])
        if "/by-product/" in req.url.path:
            return httpx.Response(200, json=[])
        if "/by-branch/" in req.url.path:
            return httpx.Response(200, json=[])
        return httpx.Response(200, json={"branches": [], "strategy": "single"})

    mcp, _, _ = _make_mcp(stock_handler=stock_handler)
    fn = _tool(mcp, "list_branches")
    await fn()
    fn = _tool(mcp, "get_product_availability")
    await fn("1")
    fn = _tool(mcp, "get_branch_inventory")
    await fn(branch_id=1)
    fn = _tool(mcp, "check_shopping_list")
    await fn(items=[{"product_id": "1", "quantity": 1}])

    assert all(t == "test-token" for t in seen_tokens)
    assert len(seen_tokens) == 4
