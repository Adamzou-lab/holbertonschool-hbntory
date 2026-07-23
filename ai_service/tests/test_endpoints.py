"""Tests des endpoints FastAPI.

Les tests utilisent TestClient + un agent et un MCP entierement mockes
(via conftest.py). Aucune cle LLM ni serveur MCP reel n'est requis.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import FakeAgent, FakeAgentRunResult

# --- /health ---


def test_health_returns_ok(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "hbntory-ai-service"
    assert "mcp_server_url" in body
    assert "llm_provider" in body
    assert "llm_model" in body


# --- /tools ---


def test_tools_lists_mcp_tools(client: TestClient) -> None:
    resp = client.get("/tools")
    assert resp.status_code == 200
    body = resp.json()
    assert "tools" in body
    names = {t["name"] for t in body["tools"]}
    assert "list_products" in names
    assert "get_product" in names
    assert "check_shopping_list" in names


def test_tools_returns_7_tools(client: TestClient) -> None:
    """Le MCP expose exactement 7 outils (3 produit + 4 stock)."""
    resp = client.get("/tools")
    assert resp.status_code == 200
    assert len(resp.json()["tools"]) == 7


# --- /query ---


def test_query_ok_simple_answer(client: TestClient, fake_agent: FakeAgent) -> None:
    fake_agent.next_result = FakeAgentRunResult(output="Je n'ai pas cette information.")
    resp = client.post("/query", json={"question": "Quel temps fait-il ?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "Je n'ai pas cette information."
    assert body["tool_calls"] == []


def test_query_with_tool_calls_recorded(client: TestClient, fake_agent: FakeAgent) -> None:
    fake_agent.next_result = FakeAgentRunResult(
        output="Paris a 50 unites, Lyon en a 5.",
        tool_calls=[
            ("list_branches", None),
            ("get_product_availability", {"product_id": "HB-LAP-1001"}),
        ],
    )
    resp = client.post("/query", json={"question": "Ou trouver HB-LAP-1001 ?"})
    assert resp.status_code == 200
    body = resp.json()
    assert "Paris" in body["answer"]
    names = [tc["tool"] for tc in body["tool_calls"]]
    assert names == ["list_branches", "get_product_availability"]
    assert body["tool_calls"][1]["args"] == {"product_id": "HB-LAP-1001"}


def test_query_rejects_empty_question(client: TestClient) -> None:
    resp = client.post("/query", json={"question": ""})
    assert resp.status_code == 422
    # FastAPI renvoie un detail sur l'erreur Pydantic
    assert "question" in resp.text.lower()


def test_query_rejects_too_long_question(client: TestClient) -> None:
    long_q = "x" * 2001
    resp = client.post("/query", json={"question": long_q})
    assert resp.status_code == 422


def test_query_rejects_missing_question_field(client: TestClient) -> None:
    resp = client.post("/query", json={})
    assert resp.status_code == 422


def test_query_returns_503_on_agent_failure(client: TestClient, fake_agent: FakeAgent) -> None:
    fake_agent.next_result = RuntimeError("LLM provider down")
    resp = client.post("/query", json={"question": "Ou est le laptop ?"})
    assert resp.status_code == 503
    assert "unavailable" in resp.text.lower()


def test_query_passes_question_to_agent(client: TestClient, fake_agent: FakeAgent) -> None:
    fake_agent.next_result = FakeAgentRunResult(output="ok")
    client.post("/query", json={"question": "Question precise de test"})
    assert fake_agent.last_question == "Question precise de test"


# --- OpenAPI ---


def test_openapi_doc_generated(client: TestClient) -> None:
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    spec = resp.json()
    assert "/query" in spec["paths"]
    assert "/health" in spec["paths"]
    assert "/tools" in spec["paths"]
