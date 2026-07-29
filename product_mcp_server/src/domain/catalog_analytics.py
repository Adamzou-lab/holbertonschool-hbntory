"""Calculs metier d'analyse catalogue (P1).

Fonctions pures, testables sans I/O.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)


def aggregate_by_category(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Agrege le catalogue par categorie. Ne transforme jamais None en 0."""
    by_cat: dict[str, dict[str, Any]] = {}
    for p in products:
        cat = (p.get("category") or "Unknown").strip() or "Unknown"
        if cat not in by_cat:
            by_cat[cat] = {
                "category": cat,
                "product_count": 0,
                "prices": [],
                "weights": [],
                "missing_price_count": 0,
                "missing_weight_count": 0,
                "currencies": set(),
            }
        bucket = by_cat[cat]
        bucket["product_count"] += 1
        price = p.get("unit_price")
        weight = p.get("weight_kg")
        currency = p.get("currency")
        if price is None:
            bucket["missing_price_count"] += 1
        else:
            bucket["prices"].append(float(price))
        if weight is None:
            bucket["missing_weight_count"] += 1
        else:
            bucket["weights"].append(float(weight))
        if currency:
            bucket["currencies"].add(currency)

    out: list[dict[str, Any]] = []
    for v in by_cat.values():
        prices = v.pop("prices")
        weights = v.pop("weights")
        cur = v.pop("currencies")
        out.append(
            {
                **v,
                "avg_price": sum(prices) / len(prices) if prices else None,
                "min_price": min(prices) if prices else None,
                "max_price": max(prices) if prices else None,
                "total_weight_kg": sum(weights) if weights else None,
                "currencies": sorted(cur),
            }
        )
    return sorted(out, key=lambda x: x["category"])


def extreme_prices(
    products: list[dict[str, Any]],
    direction: str,
    limit: int,
    category: str | None = None,
) -> list[dict[str, Any]]:
    """Top N par prix (highest ou lowest). Filtre None, conserve currency."""
    filtered = [p for p in products if p.get("unit_price") is not None]
    if category:
        filtered = [p for p in filtered if (p.get("category") or "").lower() == category.lower()]
    reverse = direction == "highest"
    filtered.sort(key=lambda p: p.get("unit_price", 0.0), reverse=reverse)
    return [
        {
            "sku": p.get("sku"),
            "name": p.get("name"),
            "category": p.get("category"),
            "unit_price": p.get("unit_price"),
            "currency": p.get("currency"),
            "weight_kg": p.get("weight_kg"),
        }
        for p in filtered[:limit]
    ]


def extreme_weights(
    products: list[dict[str, Any]],
    direction: str,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    """Top N par poids. Retourne (entries, missing_count)."""
    with_weight = [p for p in products if p.get("weight_kg") is not None]
    missing = len(products) - len(with_weight)
    reverse = direction == "heaviest"
    with_weight.sort(key=lambda p: p.get("weight_kg", 0.0), reverse=reverse)
    return (
        [
            {
                "sku": p.get("sku"),
                "name": p.get("name"),
                "category": p.get("category"),
                "weight_kg": p.get("weight_kg"),
                "unit_price": p.get("unit_price"),
            }
            for p in with_weight[:limit]
        ],
        missing,
    )


def aggregate_suppliers(
    products: list[dict[str, Any]],
    suppliers_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Agrege par fournisseur : nb produits, categories couvertes, prix moyen."""
    grouped: dict[str, dict[str, Any]] = {}
    for p in products:
        sid = p.get("supplier_id") or "unknown"
        if sid not in grouped:
            grouped[sid] = {
                "supplier_id": sid,
                "supplier_name": suppliers_by_id.get(sid, {}).get("name") or p.get("supplier_name"),
                "country": suppliers_by_id.get(sid, {}).get("country"),
                "lead_time_days": suppliers_by_id.get(sid, {}).get("lead_time_days"),
                "reliability_score": suppliers_by_id.get(sid, {}).get("reliability_score"),
                "product_count": 0,
                "categories_covered": set(),
                "prices": [],
            }
        g = grouped[sid]
        g["product_count"] += 1
        cat = p.get("category")
        if cat:
            g["categories_covered"].add(cat)
        if p.get("unit_price") is not None:
            g["prices"].append(float(p["unit_price"]))

    out: list[dict[str, Any]] = []
    for v in grouped.values():
        cats = v.pop("categories_covered")
        prices = v.pop("prices")
        v["categories_covered"] = sorted(cats)
        v["avg_price"] = sum(prices) / len(prices) if prices else None
        out.append(v)
    return sorted(out, key=lambda x: x["product_count"], reverse=True)


def estimate_inventory_value(
    products: list[dict[str, Any]],
    stock_by_product: dict[int, int],
    branches: list[dict[str, Any]],
    stock_by_product_branch: dict[int, dict[int, int]] | None = None,
) -> dict[str, Any]:
    """Estimation de la valeur catalogue du stock.

    IMPORTANT : c'est une estimation au prix catalogue (unit_price), pas un
    cout d'achat ni une marge.
    """
    by_category: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"value": 0.0, "item_count": 0, "currency": None}
    )
    by_branch: dict[int, dict[str, Any]] = {
        b["id"]: {
            "branch_id": b["id"],
            "branch_name": b.get("name"),
            "value": 0.0,
            "item_count": 0,
            "currency": None,
        }
        for b in branches
    }
    total = 0.0
    currency: str | None = None
    missing_price_count = 0

    products_by_id = {p.get("id"): p for p in products if p.get("id") is not None}
    for pid, qty in stock_by_product.items():
        if qty <= 0:
            continue
        p = products_by_id.get(pid)
        if p is None:
            continue
        price = p.get("unit_price")
        if price is None:
            missing_price_count += 1
            continue
        line_value = float(price) * qty
        total += line_value
        cat = (p.get("category") or "Unknown").strip() or "Unknown"
        by_category[cat]["value"] += line_value
        by_category[cat]["item_count"] += qty
        cur = p.get("currency")
        if cur and not by_category[cat]["currency"]:
            by_category[cat]["currency"] = cur
        if cur and not currency:
            currency = cur

        if stock_by_product_branch:
            for bid, bqty in stock_by_product_branch.get(pid, {}).items():
                if bqty <= 0 or bid not in by_branch:
                    continue
                bv = float(price) * bqty
                by_branch[bid]["value"] += bv
                by_branch[bid]["item_count"] += bqty
                if cur and not by_branch[bid]["currency"]:
                    by_branch[bid]["currency"] = cur

    return {
        "total_value": round(total, 2),
        "currency": currency,
        "missing_price_count": missing_price_count,
        "warning": "Estimation au prix catalogue. Ce n'est pas un coût d'achat ni une marge.",
        "by_category": [
            {
                **v,
                "category": cat,
                "value": round(v["value"], 2),
            }
            for cat, v in sorted(by_category.items())
        ],
        "by_branch": [
            {
                **b,
                "value": round(b["value"], 2),
            }
            for b in by_branch.values()
        ],
    }


__all__ = [
    "aggregate_by_category",
    "extreme_prices",
    "extreme_weights",
    "aggregate_suppliers",
    "estimate_inventory_value",
]
