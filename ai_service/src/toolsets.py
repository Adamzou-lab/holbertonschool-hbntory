"""Definitions des toolsets filtres pour chaque agent specialist.

Chaque agent ne recoit QUE les outils de son domaine (allowlist reelle).
Le filtrage est technique (liste explicite passee a PydanticAI), pas une
simple instruction dans le prompt.
"""

from __future__ import annotations

from dataclasses import dataclass

INVENTORY_TOOLS: frozenset[str] = frozenset(
    {
        "list_products",
        "get_product",
        "search_products",
        "list_branches",
        "get_product_availability",
        "get_branch_inventory",
        "check_shopping_list",
    }
)

ANALYTICS_TOOLS: frozenset[str] = frozenset(
    {
        "analyze_catalog_by_category",
        "find_extreme_prices",
        "find_extreme_weights",
        "analyze_supplier_portfolio",
        "estimate_catalog_stock_value",
        "assess_storage_complexity",
        "find_discontinued_with_stock",
        "analyze_stock_distribution",
        "find_overstocked_products",
        "find_understocked_products",
    }
)

FORECAST_TOOLS: frozenset[str] = frozenset(
    {
        "get_stock_history",
        "analyze_stock_trend",
        "forecast_stockout_and_reorder",
        "detect_seasonal_pattern",
    }
)

MARGIN_TOOLS: frozenset[str] = frozenset(
    {
        "compute_product_margin",
        "identify_most_profitable",
        "compute_supplier_cost",
        "analyze_storage_efficiency",
    }
)


@dataclass(frozen=True)
class ToolsetSpec:
    name: str
    tools: frozenset[str]
    public_allowed: bool


TOOLSETS: dict[str, ToolsetSpec] = {
    "inventory": ToolsetSpec("inventory", INVENTORY_TOOLS, public_allowed=True),
    "analytics": ToolsetSpec("analytics", ANALYTICS_TOOLS, public_allowed=True),
    "forecast": ToolsetSpec("forecast", FORECAST_TOOLS, public_allowed=True),
    "margin": ToolsetSpec("margin", MARGIN_TOOLS, public_allowed=False),
}


def tools_for(intent: str) -> frozenset[str]:
    spec = TOOLSETS.get(intent)
    if spec is None:
        raise ValueError(f"Unknown intent: {intent}")
    return spec.tools


def public_intents() -> list[str]:
    return [name for name, spec in TOOLSETS.items() if spec.public_allowed]


def all_intents() -> list[str]:
    return list(TOOLSETS.keys())


__all__ = [
    "INVENTORY_TOOLS",
    "ANALYTICS_TOOLS",
    "FORECAST_TOOLS",
    "MARGIN_TOOLS",
    "TOOLSETS",
    "ToolsetSpec",
    "tools_for",
    "public_intents",
    "all_intents",
]
