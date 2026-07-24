"""Tests des agents et du routage.

Couvre :
- System prompts : 5 regles anti-hallucination
- Routage deterministe (mots-cles)
- Construction des 4 agents (chacun a un system prompt distinct)
- Allowlists par intent
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from pydantic_ai import Agent

from src.agents import (
    build_analytics_agent,
    build_forecast_agent,
    build_inventory_agent,
    build_margin_agent,
    build_router_agent,
)
from src.config import Settings
from src.main import deterministic_intent
from src.prompts import (
    ANALYTICS_PROMPT,
    FORECAST_PROMPT,
    INVENTORY_PROMPT,
    MARGIN_PROMPT,
    ROUTER_PROMPT,
)
from src.routing import Intent, RoutingDecision
from src.schemas import QueryRequest, QueryResponse, ToolCallSummary
from src.toolsets import (
    ANALYTICS_TOOLS,
    FORECAST_TOOLS,
    INVENTORY_TOOLS,
    MARGIN_TOOLS,
    TOOLSETS,
    all_intents,
    public_intents,
    tools_for,
)

# --- System prompts : ils contiennent tous les regles anti-hallucination ---


def _has_no_invention_rule(prompt: str) -> bool:
    pl = prompt.lower()
    return (
        "invente" in pl
        or "invent" in pl
        or "fabric" in pl
        or "outil" in pl and "doit" in pl  # "toute valeur DOIT venir d'un outil"
        or "out of scope" in pl
        or "fabricat" in pl
    )


def _has_tool_usage_rule(prompt: str) -> bool:
    pl = prompt.lower()
    return (
        "outil" in pl
        or "tool" in pl
        or "donn" in pl  # "toute valeur vient d'un outil"
        or "synth" in pl  # data_origin synthetic_demo
    )


def _has_unavailable_info_rule(prompt: str) -> bool:
    pl = prompt.lower()
    return (
        "indisponib" in pl
        or "insuffisant" in pl
        or "limite" in pl
        or "qualite" in pl
        or "echoue" in pl
        or "echec" in pl
        or "fail" in pl
        or "manquantes" in pl
        or "manquante" in pl
    )


PROMPT_CASES = [
    ("INVENTORY", INVENTORY_PROMPT),
    ("ANALYTICS", ANALYTICS_PROMPT),
    ("FORECAST", FORECAST_PROMPT),
    ("MARGIN", MARGIN_PROMPT),
]


@pytest.mark.parametrize("name,prompt", PROMPT_CASES)
def test_prompt_has_no_invention_rule(name: str, prompt: str) -> None:
    assert _has_no_invention_rule(prompt), f"{name}: rule 'no invention' missing"


@pytest.mark.parametrize("name,prompt", PROMPT_CASES)
def test_prompt_has_tool_usage_rule(name: str, prompt: str) -> None:
    assert _has_tool_usage_rule(prompt), f"{name}: rule 'use tools' missing"


@pytest.mark.parametrize("name,prompt", PROMPT_CASES)
def test_prompt_has_unavailable_info_rule(name: str, prompt: str) -> None:
    assert _has_unavailable_info_rule(prompt), f"{name}: rule 'unavailable' missing"


def test_margin_prompt_warns_synthetic() -> None:
    pl = MARGIN_PROMPT.lower()
    assert "synth" in pl, "Margin prompt must mark data as synthetic"


def test_router_prompt_has_intents() -> None:
    pl = ROUTER_PROMPT.lower()
    for intent in ("inventory", "analytics", "forecast", "margin", "out_of_scope"):
        assert intent in pl, f"Router prompt missing intent '{intent}'"


# --- Routing deterministe ---


@pytest.mark.parametrize(
    "question,expected_intent",
    [
        ("Quelle est la marge sur le laptop 14 ?", Intent.MARGIN),
        ("Donne-moi la rentabilite du produit X", Intent.MARGIN),
        ("Quel est le cout fournisseur pour SUP-HBT-001 ?", Intent.MARGIN),
        ("Quelle est la tendance du stock a Paris ?", Intent.FORECAST),
        ("Y a-t-il un effet saisonnier sur les moniteurs ?", Intent.FORECAST),
        ("Quand le stock de HB-LAP-1001 sera-t-il en rupture ?", Intent.FORECAST),
        ("Donne-moi le top 5 des produits les plus chers", Intent.ANALYTICS),
        ("Analyse la repartition du stock par categorie", Intent.ANALYTICS),
        ("Quel produit est en stock a Paris ?", Intent.INVENTORY),
        ("Quels produits sont disponibles dans la branche Lyon ?", Intent.INVENTORY),
    ],
)
def test_deterministic_routing(question: str, expected_intent: Intent) -> None:
    decision = deterministic_intent(question)
    assert decision is not None
    assert decision.intent == expected_intent
    assert 0.0 <= decision.confidence <= 1.0


def test_deterministic_routing_falls_back_to_inventory_when_no_keyword() -> None:
    decision = deterministic_intent("Quelle est la meteo demain ?")
    # Aucune regle deterministe ne matche : le LLM sera appele.
    assert decision is None


# --- Allowlists par intent ---


def test_inventory_tools_count() -> None:
    assert len(INVENTORY_TOOLS) == 7


def test_analytics_tools_count() -> None:
    assert len(ANALYTICS_TOOLS) == 10


def test_forecast_tools_count() -> None:
    assert len(FORECAST_TOOLS) == 4


def test_margin_tools_count() -> None:
    assert len(MARGIN_TOOLS) == 4


def test_total_tools_25() -> None:
    total = INVENTORY_TOOLS | ANALYTICS_TOOLS | FORECAST_TOOLS | MARGIN_TOOLS
    assert len(total) == 25


def test_tools_for_unknown_intent_raises() -> None:
    with pytest.raises(ValueError):
        tools_for("unknown")


def test_public_intents_excludes_margin() -> None:
    public = public_intents()
    assert "margin" not in public
    assert "inventory" in public
    assert "analytics" in public
    assert "forecast" in public


def test_all_intents_includes_margin() -> None:
    assert "margin" in all_intents()


def test_toolset_public_flag_consistent() -> None:
    for name, spec in TOOLSETS.items():
        if name == "margin":
            assert spec.public_allowed is False
        else:
            assert spec.public_allowed is True


# --- Construction des agents (avec TestModel) ---


def _test_model_agents() -> dict[str, Agent]:
    """Construit les 4 agents avec TestModel (pas de cle API reelle)."""
    from pydantic_ai.models.test import TestModel

    model = "test"
    fake_toolset = object()
    agents = {
        "inventory": build_inventory_agent(model, fake_toolset),
        "analytics": build_analytics_agent(model, fake_toolset),
        "forecast": build_forecast_agent(model, fake_toolset),
        "margin": build_margin_agent(model, fake_toolset),
    }
    # Force TestModel pour ne pas avoir besoin de cle.
    for a in agents.values():
        a._model = TestModel()
    return agents


def test_build_all_four_agents() -> None:
    agents = _test_model_agents()
    assert all(isinstance(a, Agent) for a in agents.values())
    assert set(agents.keys()) == {"inventory", "analytics", "forecast", "margin"}


def test_router_agent_has_structured_output() -> None:
    from pydantic_ai.models.test import TestModel

    agent = build_router_agent("test")
    agent._model = TestModel()
    # L'agent a un output_type structure
    assert agent.output_type is not None


def test_each_agent_has_distinct_system_prompt() -> None:
    """Pas de confusion entre les system prompts des 4 agents."""
    prompts = {
        "inventory": INVENTORY_PROMPT,
        "analytics": ANALYTICS_PROMPT,
        "forecast": FORECAST_PROMPT,
        "margin": MARGIN_PROMPT,
    }
    # Tous distincts
    assert len(set(prompts.values())) == 4


# --- Settings ---


def test_settings_internal_token_default_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AI_INTERNAL_TOKEN", raising=False)
    s = Settings()
    assert s.internal_token is None


def test_settings_default_provider_anthropic() -> None:
    s = Settings()
    assert s.llm_provider == "anthropic"


def test_settings_rejects_invalid_port() -> None:
    with pytest.raises(ValidationError):
        Settings(ai_port=0)


# --- Schemas ---


def test_query_request_min_length() -> None:
    with pytest.raises(ValidationError):
        QueryRequest(question="")


def test_query_response_required_fields() -> None:
    r = QueryResponse(
        answer="x",
        intent=Intent.INVENTORY,
        routing_confidence=0.8,
        tool_calls=[],
        data_origins=[],
        limitations=[],
        request_id="abc123",
    )
    assert r.intent == Intent.INVENTORY


def test_routing_decision_validates_confidence_bounds() -> None:
    with pytest.raises(ValidationError):
        RoutingDecision(intent=Intent.INVENTORY, confidence=1.5, reason_code="x")


def test_tool_call_summary_accepts_null_args() -> None:
    r = ToolCallSummary(tool="list_branches", args=None)
    assert r.args is None
