"""Fixtures pytest partagees.

Les tests du Service IA ne requierent ni cle LLM ni serveur MCP live :
on mocke systematiquement l'agent PydanticAI et le MCPToolset.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.config import Settings
from src.main import app

# Ajoute la racine du projet au sys.path pour permettre l'import du Bloc 2
# dans les tests d'integration (product_mcp_server).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


@pytest.fixture(autouse=True)
def _set_fake_llm_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fournit des cles API factices pour que PydanticAI puisse instancier
    un Agent sans verifier la cle reelle (on remontera jamais jusqu'a l'API
    dans les tests, soit parce qu'on mock l'agent, soit parce qu'on utilise
    TestModel en post-instantiation)."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-used")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-used")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key-not-used")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")


class FakeMCPToolset:
    """Mock minimal d'un MCPToolset pour eviter toute connexion reseau."""

    async def __aenter__(self) -> FakeMCPToolset:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    async def get_tools(self) -> dict[str, Any]:
        return {
            "list_products": object(),
            "get_product": object(),
            "search_products": object(),
            "list_branches": object(),
            "get_product_availability": object(),
            "get_branch_inventory": object(),
            "check_shopping_list": object(),
        }


class FakeMCPConnection:
    """Mock de MCPConnection utilisee dans le lifespan."""

    def __init__(self) -> None:
        self.toolset = FakeMCPToolset()

    @classmethod
    async def connect(cls, settings: Settings) -> FakeMCPConnection:
        return cls()

    async def close(self) -> None:
        pass

    async def list_tool_names(self) -> list[str]:
        return list((await self.toolset.get_tools()).keys())


class FakeAgentRunResult:
    """Mock d'un AgentRunResult PydanticAI."""

    def __init__(self, output: str, tool_calls: list[tuple[str, dict | None]] | None = None) -> None:
        self.output = output
        self._tool_calls = tool_calls or []

        # Simule all_messages() en retournant des objets .parts compatibles.
        class _Part:
            def __init__(self, name: str, args: dict | None) -> None:
                self.part_kind = "tool-call"
                self.tool_name = name
                self.tool_call_id = name
                self.args = args

        class _Msg:
            def __init__(self, parts: list[_Part]) -> None:
                self.parts = parts

        self._msgs = []
        for name, args in self._tool_calls:
            self._msgs.append(_Msg([_Part(name, args)]))

    def all_messages(self) -> list[Any]:
        return self._msgs


class FakeAgent:
    """Mock d'un Agent PydanticAI : on controle sa reponse via `next_result`."""

    def __init__(self) -> None:
        self.next_result: FakeAgentRunResult | Exception = FakeAgentRunResult("ok")
        self.last_question: str | None = None

    async def run(self, question: str) -> FakeAgentRunResult:
        self.last_question = question
        if isinstance(self.next_result, Exception):
            raise self.next_result
        return self.next_result


@pytest.fixture
def fake_agent() -> FakeAgent:
    return FakeAgent()


@pytest.fixture
def fake_mcp() -> FakeMCPConnection:
    return FakeMCPConnection()


@pytest.fixture
def client(fake_agent: FakeAgent, fake_mcp: FakeMCPConnection, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """TestClient FastAPI avec lifespan reellement execute mais agent/mcp mockes.

    Le lifespan ouvre une vraie connexion MCP dans la prod. Ici on monkey-patch
    MCPConnection.connect et build_agent pour eviter toute I/O.
    """

    from src import main as main_module

    async def fake_connect(settings: Settings) -> FakeMCPConnection:
        return fake_mcp

    def fake_build_agent(settings: Settings, mcp: Any) -> FakeAgent:
        return fake_agent

    monkeypatch.setattr(main_module, "MCPConnection", FakeMCPConnection)
    monkeypatch.setattr(main_module, "build_agent", fake_build_agent)

    with TestClient(app) as c:
        yield c
