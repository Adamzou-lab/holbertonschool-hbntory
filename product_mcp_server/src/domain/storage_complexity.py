"""Heuristique de complexite de stockage (P1).

Score 0..100. Somme ponderee de 4 facteurs :

- poids (40%)
- risque categorie (30%)
- discontinue (20%)
- tags (10%)

Versionnee (heuristic_v1) pour faciliter l'evolution.
"""

from __future__ import annotations

from typing import Any

HIGH_RISK_CATEGORIES = {"furniture", "power"}
MEDIUM_RISK_CATEGORIES = {"audio", "displays", "development kits"}
HIGH_RISK_TAGS = {"legacy", "fragile", "hazardous"}

METHODOLOGY = "heuristic_v1"


def _score_weight(weight_kg: float | None) -> float:
    if weight_kg is None:
        return 0.0
    return min(weight_kg / 20.0, 1.0) * 100.0


def _score_category(category: str | None) -> float:
    if not category:
        return 0.0
    c = category.strip().lower()
    if c in HIGH_RISK_CATEGORIES:
        return 80.0
    if c in MEDIUM_RISK_CATEGORIES:
        return 50.0
    return 20.0


def _score_discontinued(discontinued: bool) -> float:
    return 100.0 if discontinued else 0.0


def _score_tags(tags: list[str]) -> float:
    if not tags:
        return 10.0
    if any(t.lower() in HIGH_RISK_TAGS for t in tags):
        return 80.0
    return 10.0


def assess_complexity(product: dict[str, Any]) -> tuple[int, dict[str, float]]:
    """Renvoie (score, facteurs) pour un produit (dict brut API)."""
    weight = product.get("weight_kg")
    cat = product.get("category")
    disc = bool(product.get("discontinued"))
    tags = list(product.get("tags") or [])

    fs = {
        "weight_score": round(_score_weight(weight), 2),
        "category_risk_score": round(_score_category(cat), 2),
        "discontinued_score": round(_score_discontinued(disc), 2),
        "tags_score": round(_score_tags(tags), 2),
        "methodology": METHODOLOGY,
    }
    score = int(
        0.4 * fs["weight_score"]
        + 0.3 * fs["category_risk_score"]
        + 0.2 * fs["discontinued_score"]
        + 0.1 * fs["tags_score"]
    )
    score = max(0, min(100, score))
    return score, fs


__all__ = ["assess_complexity", "METHODOLOGY"]
