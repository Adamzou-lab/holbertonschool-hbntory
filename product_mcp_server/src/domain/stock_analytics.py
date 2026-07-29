"""Calculs metier d'analyse stock (P1)."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)


def stock_distribution(
    stock_by_product_branch: dict[int, dict[int, int]],
    branches: list[dict[str, Any]],
    products_by_id: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    """Repartition du stock par branche + indice de concentration (Gini)."""
    by_branch_total: dict[int, int] = defaultdict(int)
    by_branch_items: dict[int, int] = defaultdict(int)
    cat_units: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for pid, per_branch in stock_by_product_branch.items():
        p = products_by_id.get(pid, {})
        cat = (p.get("category") or "Unknown").strip() or "Unknown"
        for bid, qty in per_branch.items():
            if qty <= 0:
                continue
            by_branch_total[bid] += qty
            by_branch_items[bid] += 1
            cat_units[bid][cat] += qty

    by_branch = []
    for b in branches:
        bid = b["id"]
        cats = cat_units.get(bid, {})
        top = sorted(cats.items(), key=lambda x: x[1], reverse=True)[:3]
        by_branch.append(
            {
                "branch_id": bid,
                "branch_name": b.get("name"),
                "total_items": by_branch_items[bid],
                "total_units": by_branch_total[bid],
                "top_categories": [{"category": c, "units": u} for c, u in top],
            }
        )

    totals = sorted(by_branch_total.values())
    gini = _gini(totals)
    grand_total = sum(totals)
    top_share = max(totals) / grand_total if grand_total else 0.0

    return {
        "by_branch": by_branch,
        "concentration": {
            "gini_index": round(gini, 4),
            "top_branch_share": round(top_share, 4),
            "method": "absolute_units",
        },
    }


def find_overstocked(
    stock_by_product_branch: dict[int, dict[int, int]],
    threshold: int,
    limit: int,
) -> list[dict[str, Any]]:
    """Produits dont le stock total depasse le seuil (methode simple)."""
    rows = []
    for pid, per_branch in stock_by_product_branch.items():
        total = sum(q for q in per_branch.values() if q > 0)
        if total < threshold:
            continue
        rows.append(
            {
                "product_id": pid,
                "total_units": total,
                "branches": [
                    {"branch_id": bid, "quantity": q}
                    for bid, q in per_branch.items()
                    if q > 0
                ],
            }
        )
    rows.sort(key=lambda r: r["total_units"], reverse=True)
    return rows[:limit]


def find_understocked(
    stock_by_product_branch: dict[int, dict[int, int]],
    threshold: int,
    limit: int,
    category: str | None = None,
    products_by_id: dict[int, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Produits dont le stock total est sous le seuil."""
    rows = []
    for pid, per_branch in stock_by_product_branch.items():
        total = sum(q for q in per_branch.values() if q > 0)
        if total >= threshold:
            continue
        if category and products_by_id:
            p = products_by_id.get(pid, {})
            if (p.get("category") or "").lower() != category.lower():
                continue
        rows.append(
            {
                "product_id": pid,
                "total_units": total,
                "branches": [
                    {"branch_id": bid, "quantity": q}
                    for bid, q in per_branch.items()
                    if q > 0
                ],
            }
        )
    rows.sort(key=lambda r: r["total_units"])
    return rows[:limit]


def _gini(values: list[int]) -> float:
    """Indice de Gini (0 = egalitaire, 1 = monopolistique). Renvoie 0 si vide."""
    if not values or sum(values) == 0:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    cum = 0.0
    total = sum(sorted_vals)
    for i, v in enumerate(sorted_vals, start=1):
        cum += i * v
    return (2.0 * cum) / (n * total) - (n + 1) / n


__all__ = [
    "stock_distribution",
    "find_overstocked",
    "find_understocked",
    "_gini",
]
