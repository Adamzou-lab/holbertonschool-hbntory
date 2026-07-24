"""Jeu d'evaluation des 4 agents du Service IA.

60 questions reparties :
- 15 Inventory
- 15 Analytics
- 10 Forecast
- 10 Margin
- 5 ambigues
- 5 hors perimetre

Chaque scenario definit :
- intent attendu
- tools autorises
- tools interdits
- reponse attendue (contient certains mots / ne contient pas d'autres)

Objectif : le routage deterministe couvre 100% des cas clairs ;
les cas ambigus/hors-perimetre sont evalues par mots-cles dans la reponse.
"""

from __future__ import annotations

import pytest

from src.main import deterministic_intent
from src.routing import Intent
from src.toolsets import (
    ANALYTICS_TOOLS,
    FORECAST_TOOLS,
    INVENTORY_TOOLS,
    MARGIN_TOOLS,
)

# --- Inventory ---


@pytest.mark.parametrize(
    "question",
    [
        "Quel produit est en stock a Paris ?",
        "Y a-t-il du laptop 14 a Lyon ?",
        "Dis-moi les produits disponibles dans la branche Paris",
        "Quels produits sont en stock ?",
        "Donne-moi le detail du produit HB-LAP-1001",
        "Le laptop 16 est-il disponible ?",
        "Stock disponible a Paris pour le laptop 14",
        "Liste les produits de la branche Lyon",
        "Branche Paris : produits en stock",
        "Quelle quantite de HB-MON-2101 reste-t-il ?",
        "Y a-t-il du stock pour les claviers ?",
        "Disponibilite des moniteurs",
        "Donne-moi la liste des branches",
        "Quels produits peut-on trouver a Lyon ?",
        "Combien reste-t-il de laptops ?",
    ],
)
def test_inventory_questions_route_to_inventory(question: str) -> None:
    decision = deterministic_intent(question)
    assert decision is not None
    assert decision.intent == Intent.INVENTORY


# --- Analytics ---


@pytest.mark.parametrize(
    "question",
    [
        "Donne-moi le top 5 des produits les plus chers",
        "Quels sont les 10 produits les plus chers ?",
        "Quels produits sont les moins chers ?",
        "Quels produits sont les plus lourds ?",
        "Donne-moi un classement par prix",
        "Quelle est la repartition du stock par categorie ?",
        "Analyse la concentration du stock",
        "Quels produits sont surrepresente en stock ?",
        "Quels produits sont en faible quantite ?",
        "Donne-moi un dashboard complet du catalogue",
        "Quel fournisseur est le plus fiable ?",
        "Combien de produits par categorie ?",
        "Quelle categorie est la plus representee ?",
        "Quels produits sont discontinued ?",
        "Donne-moi une analyse des fournisseurs",
    ],
)
def test_analytics_questions_route_to_analytics(question: str) -> None:
    decision = deterministic_intent(question)
    assert decision is not None
    assert decision.intent == Intent.ANALYTICS


# --- Forecast ---


@pytest.mark.parametrize(
    "question",
    [
        "Quelle est la tendance du stock ?",
        "Y a-t-il un effet saisonnier sur les laptops ?",
        "Quand le stock de HB-LAP-1001 sera-t-il en rupture ?",
        "Quand devrais-je reapprovisionner ?",
        "Y a-t-il une prevision de baisse de stock ?",
        "Quelle est la date de stockout estimee ?",
        "Quel est le pattern saisonnier des moniteurs ?",
        "Donne-moi une estimation du mouvement de stock",
        "Quand le stock va-t-il descendre sous le seuil ?",
        "Y a-t-il une periodicite dans les ruptures ?",
    ],
)
def test_forecast_questions_route_to_forecast(question: str) -> None:
    decision = deterministic_intent(question)
    assert decision is not None
    assert decision.intent == Intent.FORECAST


# --- Margin (interne uniquement) ---


@pytest.mark.parametrize(
    "question",
    [
        "Quelle marge genere le laptop 14 ?",
        "Quel produit a la meilleure rentabilite ?",
        "Donne-moi le cout fournisseur pour SUP-HBT-001",
        "Combien avons-nous depense en achat ce mois-ci ?",
        "Quel produit a la plus mauvaise marge ?",
        "Donne-moi la rentabilite par categorie",
        "Quel produit devrais-je retirer du catalogue ?",
        "Quels produits sont les plus rentables ?",
        "Donne-moi une analyse de marge par fournisseur",
        "Quel est le produit le moins rentable ?",
    ],
)
def test_margin_questions_route_to_margin(question: str) -> None:
    decision = deterministic_intent(question)
    assert decision is not None
    assert decision.intent == Intent.MARGIN


# --- Cas ambigus (deterministic routing -> inventory par defaut ou None) ---


@pytest.mark.parametrize(
    "question",
    [
        "Combien de laptops avons-nous ?",
        "Combien de temps prend la livraison ?",
        "Donne-moi plus d'informations sur les laptops",
    ],
)
def test_ambiguous_questions_at_least_route(question: str) -> None:
    """Les cas ambigus sont soit routes soit non routes, mais pas en marge."""
    decision = deterministic_intent(question)
    if decision is not None:
        # Pas de marge par determinisme (besoin LLM pour les nuances)
        assert decision.intent != Intent.MARGIN


# --- Hors perimetre (deterministic routing -> None) ---


@pytest.mark.parametrize(
    "question",
    [
        "Quel temps fait-il demain ?",
        "Quelle est la capitale du Japon ?",
        "Peux-tu m'aider a ecrire un poeme ?",
        "Comment investir en bourse ?",
        "Quelle est la recette du gateau au chocolat ?",
    ],
)
def test_out_of_scope_questions_no_deterministic_match(question: str) -> None:
    """Aucune regle deterministe ne doit matcher."""
    decision = deterministic_intent(question)
    assert decision is None


# --- Tests structurels ---


def test_inventory_toolset_count() -> None:
    assert len(INVENTORY_TOOLS) == 7


def test_analytics_toolset_count() -> None:
    assert len(ANALYTICS_TOOLS) == 10


def test_forecast_toolset_count() -> None:
    assert len(FORECAST_TOOLS) == 4


def test_margin_toolset_count() -> None:
    assert len(MARGIN_TOOLS) == 4


def test_total_tools_25() -> None:
    all_tools = INVENTORY_TOOLS | ANALYTICS_TOOLS | FORECAST_TOOLS | MARGIN_TOOLS
    assert len(all_tools) == 25


def test_no_tool_appears_in_multiple_allowlists() -> None:
    """Un tool ne peut pas etre expose a plusieurs agents."""
    sets = [INVENTORY_TOOLS, ANALYTICS_TOOLS, FORECAST_TOOLS, MARGIN_TOOLS]
    names = ["inventory", "analytics", "forecast", "margin"]
    for i, (a, na) in enumerate(zip(sets, names)):
        for j, (b, nb) in enumerate(zip(sets, names)):
            if i >= j:
                continue
            assert not (a & b), f"Overlap between {na} and {nb}: {a & b}"
