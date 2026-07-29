"""Tests des endpoints FastAPI du Service IA multi-agent.

Strategy : TestClient + monkeypatch sur le lifespan pour eviter toute
connexion LLM / MCP reelle. Les agents et le routeur sont substitues par
des fakes deterministes.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.main import app


class FakeAgentRunResult:
    def __init__(self, output: str, tool_calls: list[tuple[str, dict | None]] | None = None) -> None:
        self.output = output
        self._tcs = tool_calls or []

        class _Part:
            def __init__(self, name: str, args: dict | None) -> None:
                self.part_kind = "tool-call"
                self.tool_name = name
                self.tool_call_id = name
                self.args = args

        class _Msg:
            def __init__(self, parts: list[_Part]) -> None:
                self.parts = parts

        self._msgs = [_Msg([_Part(name, args) for name, args in self._tcs])]

    def all_messages(self) -> list[Any]:
        return self._msgs


class FakeAgent:
    """Fake Agent PydanticAI controllant la reponse et capturant la question."""

    def __init__(self, output: str = "ok", tool_calls: list[tuple[str, dict | None]] | None = None) -> None:
        self.output = output
        self.tool_calls = tool_calls
        self.next_exc: Exception | None = None

    async def run(self, question: str) -> FakeAgentRunResult:
        if self.next_exc:
            raise self.next_exc
        return FakeAgentRunResult(self.output, self.tool_calls)


class FakeRouterAgent:
    """Fake du routeur : renvoie une decision determinee."""

    def __init__(self, intent: str = "inventory") -> None:
        from src.routing import Intent, RoutingDecision

        self._decision = RoutingDecision(intent=Intent(intent), confidence=0.9, reason_code="test")

    async def run(self, question: str) -> Any:

        class _Result:
            output = self._decision

        return _Result()


class FakeMCPConnection:
    def __init__(self) -> None:
        self.toolset = object()

    @classmethod
    async def connect(cls, settings: Any) -> FakeMCPConnection:
        return cls()

    async def close(self) -> None:
        pass

    async def list_tool_names(self) -> list[str]:
        return [
            "list_products", "get_product", "search_products",
            "list_branches", "get_product_availability", "get_branch_inventory",
            "check_shopping_list",
            "analyze_catalog_by_category", "find_extreme_prices", "find_extreme_weights",
            "analyze_supplier_portfolio", "estimate_catalog_stock_value",
            "assess_storage_complexity", "find_discontinued_with_stock",
            "analyze_stock_distribution", "find_overstocked_products",
            "find_understocked_products",
            "get_stock_history", "analyze_stock_trend", "forecast_stockout_and_reorder",
            "detect_seasonal_pattern",
            "compute_product_margin", "identify_most_profitable",
            "compute_supplier_cost", "analyze_storage_efficiency",
        ]


@pytest.fixture
def agents() -> dict[str, FakeAgent]:
    return {
        "inventory": FakeAgent("inventaire: ok"),
        "analytics": FakeAgent("analytics: ok"),
        "forecast": FakeAgent("forecast: ok"),
        "margin": FakeAgent("margin: ok", tool_calls=[("compute_product_margin", {"product_id": "1"})]),
    }


@pytest.fixture
def router() -> FakeRouterAgent:
    return FakeRouterAgent(intent="inventory")


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch,
    agents: dict[str, FakeAgent],
    router: FakeRouterAgent,
) -> TestClient:
    from src import main as main_module
    from src.config import get_settings

    # Configure un token interne deterministe pour les tests /internal/query
    monkeypatch.setenv("AI_INTERNAL_TOKEN", "test-internal-secret")

    async def fake_connect(settings: Any) -> FakeMCPConnection:
        return FakeMCPConnection()

    monkeypatch.setattr(main_module, "MCPConnection", FakeMCPConnection)
    monkeypatch.setattr(main_module, "build_inventory_agent", lambda *a, **kw: agents["inventory"])
    monkeypatch.setattr(main_module, "build_analytics_agent", lambda *a, **kw: agents["analytics"])
    monkeypatch.setattr(main_module, "build_forecast_agent", lambda *a, **kw: agents["forecast"])
    monkeypatch.setattr(main_module, "build_margin_agent", lambda *a, **kw: agents["margin"])
    monkeypatch.setattr(main_module, "build_router_agent", lambda *a, **kw: router)

    # Reset settings cache
    if hasattr(get_settings, "cache_clear"):
        get_settings.cache_clear()

    with TestClient(app) as c:
        yield c


# --- /health ---


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "hbntory-ai-service"


# --- /tools ---


def test_tools_lists_25_tools(client: TestClient) -> None:
    r = client.get("/tools")
    assert r.status_code == 200
    assert len(r.json()["tools"]) == 25


# --- /query (public) ---


def test_query_inventory_routes_to_inventory_agent(
    client: TestClient, agents: dict[str, FakeAgent]
) -> None:
    r = client.post("/query", json={"question": "Quel produit est en stock a Paris ?"})
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "inventory"
    assert "inventaire" in body["answer"]


def test_query_out_of_scope_returns_refusal(client: TestClient, router: FakeRouterAgent) -> None:
    from src.routing import Intent, RoutingDecision

    # Force le routeur a renvoyer OUT_OF_SCOPE (le mot "temps" n'est dans aucune regle deterministe)
    router._decision = RoutingDecision(intent=Intent.OUT_OF_SCOPE, confidence=0.95, reason_code="forced")
    r = client.post("/query", json={"question": "Quel temps fait-il ?"})
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "out_of_scope"
    assert "specialise" in body["answer"]


def test_query_analytics_routes_via_deterministic(
    client: TestClient, agents: dict[str, FakeAgent]
) -> None:
    r = client.post("/query", json={"question": "Donne-moi le top 5 des produits les plus chers"})
    assert r.status_code == 200
    assert r.json()["intent"] == "analytics"


def test_query_forecast_routes_via_deterministic(
    client: TestClient, agents: dict[str, FakeAgent]
) -> None:
    r = client.post("/query", json={"question": "Quelle est la tendance du stock ?"})
    assert r.status_code == 200
    assert r.json()["intent"] == "forecast"


def test_query_margin_blocked_on_public_endpoint(
    client: TestClient, agents: dict[str, FakeAgent], router: FakeRouterAgent
) -> None:
    # Force le routeur a renvoyer MARGIN
    from src.routing import Intent, RoutingDecision

    router._decision = RoutingDecision(intent=Intent.MARGIN, confidence=0.95, reason_code="forced")
    r = client.post("/query", json={"question": "Quelle marge sur le produit X ?"})
    assert r.status_code == 200
    body = r.json()
    # L'implementation renvoie le refus "reserve aux appels internes" avec intent=marginet limitations.
    assert body["intent"] == "margin"
    assert any("margin_restricted" in lim for lim in body["limitations"])


def test_query_records_tool_calls(
    client: TestClient, agents: dict[str, FakeAgent]
) -> None:
    agents["inventory"].output = "result"
    agents["inventory"].tool_calls = [("list_branches", None)]
    r = client.post("/query", json={"question": "Quel produit est en stock ?"})
    body = r.json()
    assert any(tc["tool"] == "list_branches" for tc in body["tool_calls"])


def test_query_empty_question_422(client: TestClient) -> None:
    r = client.post("/query", json={"question": ""})
    assert r.status_code == 422


def test_query_too_long_question_422(client: TestClient) -> None:
    r = client.post("/query", json={"question": "x" * 2001})
    assert r.status_code == 422


def test_query_agent_failure_returns_503(
    client: TestClient, agents: dict[str, FakeAgent]
) -> None:
    agents["inventory"].next_exc = RuntimeError("LLM down")
    r = client.post("/query", json={"question": "Quel produit en stock ?"})
    assert r.status_code == 503


# --- /internal/query ---


def test_internal_query_requires_token(client: TestClient) -> None:
    r = client.post("/internal/query", json={"question": "Quel stock ?"})
    assert r.status_code == 401


def test_internal_query_rejects_wrong_token(client: TestClient) -> None:
    r = client.post(
        "/internal/query",
        json={"question": "Quel stock ?"},
        headers={"X-Internal-Token": "wrong"},
    )
    assert r.status_code == 401


def test_internal_query_with_correct_token(
    client: TestClient, agents: dict[str, FakeAgent]
) -> None:
    r = client.post(
        "/internal/query",
        json={"question": "Quel produit est en stock ?"},
        headers={"X-Internal-Token": "test-internal-secret"},
    )
    assert r.status_code == 200


def test_internal_query_allows_margin(
    client: TestClient, agents: dict[str, FakeAgent], router: FakeRouterAgent
) -> None:
    from src.routing import Intent, RoutingDecision

    router._decision = RoutingDecision(intent=Intent.MARGIN, confidence=0.95, reason_code="forced")
    r = client.post(
        "/internal/query",
        json={"question": "Marge sur le produit X ?"},
        headers={"X-Internal-Token": "test-internal-secret"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "margin"
    assert "synthetic_demo" in body["data_origins"]


# --- OpenAPI ---


def test_openapi_includes_new_endpoints(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    paths = spec["paths"]
    assert "/query" in paths
    assert "/internal/query" in paths
    assert "/health" in paths
    assert "/tools" in paths
