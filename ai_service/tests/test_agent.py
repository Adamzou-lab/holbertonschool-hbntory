"""Tests de l'agent (construction + system prompt)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from src.agent import build_agent
from src.config import Settings
from src.prompts import SYSTEM_PROMPT
from src.schemas import QueryRequest, QueryResponse, ToolCallRecord
from tests.conftest import FakeMCPConnection

# --- System prompt ---


def test_system_prompt_mentions_no_hallucination_rule() -> None:
    """Le system prompt doit contenir la regle anti-hallucination."""
    assert "invente" in SYSTEM_PROMPT.lower() or "invent" in SYSTEM_PROMPT.lower()


def test_system_prompt_mentions_tool_usage() -> None:
    assert "outil" in SYSTEM_PROMPT.lower() or "tool" in SYSTEM_PROMPT.lower()


def test_system_prompt_mentions_scope_refusal() -> None:
    """Le system prompt doit expliquer comment refuser une question hors perimetre."""
    assert "perimetre" in SYSTEM_PROMPT.lower() or "hors" in SYSTEM_PROMPT.lower()


def test_system_prompt_mentions_unavailable_info() -> None:
    """Le system prompt doit explicitement dire 'je n'ai pas l'info'."""
    assert (
        "je n'ai pas" in SYSTEM_PROMPT.lower()
        or "je n\u2019ai pas" in SYSTEM_PROMPT.lower()
        or "indisponible" in SYSTEM_PROMPT.lower()
    )


# --- build_agent (avec TestModel pour eviter une vraie cle API) ---


def _build_test_agent(provider: str = "anthropic", model: str = "claude-3-5-sonnet-latest") -> Agent:
    """Construit un agent en forcant le modele sur TestModel (pas de cle requise)."""
    s = Settings(llm_provider=provider, llm_model=model)
    mcp = FakeMCPConnection()
    agent = build_agent(s, mcp)
    # On remplace par un TestModel (pas d'appel reseau).
    agent._model = TestModel()  # type: ignore[attr-defined]
    return agent


def test_build_agent_returns_pydanticai_agent() -> None:
    agent = _build_test_agent()
    assert isinstance(agent, Agent)


def test_build_agent_attaches_mcp_toolset() -> None:
    agent = _build_test_agent()
    assert len(agent.toolsets) >= 1


def test_build_agent_uses_system_prompt() -> None:
    agent = _build_test_agent()
    # Le system prompt est stocke dans _system_prompts (tuple)
    prompts = getattr(agent, "_system_prompts", ()) or ()
    full = " ".join(p for p in prompts if isinstance(p, str))
    assert "HBntory" in full or "inventaire" in full.lower()


def test_build_agent_supports_multiple_providers() -> None:
    """Meme si on utilise TestModel, on verifie que le code accepte d'autres providers."""
    for provider, model in [
        ("anthropic", "claude-3-5-sonnet-latest"),
        ("openai", "gpt-4o"),
        ("google", "gemini-2.0-flash"),
        ("ollama", "llama3.2"),
    ]:
        agent = _build_test_agent(provider, model)
        agent._model = TestModel()  # type: ignore[attr-defined]
        assert isinstance(agent, Agent)


# --- Settings ---


def test_settings_default_provider_is_anthropic() -> None:
    s = Settings()
    assert s.llm_provider == "anthropic"


def test_settings_default_model_is_claude() -> None:
    s = Settings()
    assert "claude" in s.llm_model.lower()


def test_settings_exposes_mcp_url() -> None:
    s = Settings(mcp_server_url="http://example.test:1234/mcp")
    assert s.mcp_server_url == "http://example.test:1234/mcp"


def test_settings_rejects_invalid_port() -> None:
    with pytest.raises(ValidationError):
        Settings(ai_port=0)


# --- Schemas ---


def test_query_request_min_length() -> None:
    with pytest.raises(ValidationError):
        QueryRequest(question="")


def test_query_response_default_tool_calls_empty() -> None:
    r = QueryResponse(answer="x", tool_calls=[])
    assert r.tool_calls == []
    assert isinstance(r.tool_calls, list)


def test_tool_call_record_accepts_null_args() -> None:
    r = ToolCallRecord(tool="list_branches", args=None)
    assert r.args is None
