"""Outils MCP Margin (4 tools, P3).

Donnees synthetiques via FixtureProfitabilityProvider. Tous les calculs
monetaires utilisent Decimal. Les reponses mentionnent explicitement
``data_origin = synthetic_demo``.

L'agent IA ne doit JAMAIS presenter ces chiffres comme des donnees
commerciales reelles.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ..domain.cache import CATALOG_CACHE
from ..domain.pagination import DEFAULT_PAGE_SIZE, paginate_all
from ..domain.profitability import (
    aggregate_supplier_cost,
    build_storage_efficiency,
    compute_product_margin,
    rank_products,
)
from ..domain.storage_complexity import assess_complexity
from ..errors import MCPServiceError, ResolverError, to_tool_error
from ..providers.profitability_base import ProfitabilityDataProvider
from ..resolvers import resolve_product_id_cached
from ..schemas.margin import ProfitabilityMetric

if TYPE_CHECKING:
    from ..clients.product_client import ProductClient

logger = logging.getLogger(__name__)


async def _load_products_by_id(
    product_client: ProductClient,
) -> tuple[dict[int, dict[str, Any]], dict[int, str]]:
    async def real_compute() -> list[dict[str, Any]]:
        return await paginate_all(
            lambda offset, limit: product_client.list_products(offset=offset, limit=limit),
            page_size=DEFAULT_PAGE_SIZE,
            results_key="products",
        )

    products, _ = await CATALOG_CACHE.get_or_compute("catalog:full", real_compute)
    out: dict[int, dict[str, Any]] = {}
    names: dict[int, str] = {}
    for p in products:
        pid = p.get("id")
        if isinstance(pid, int):
            out[pid] = p
            names[pid] = p.get("name") or f"Product {pid}"
    return out, names


def register(
    mcp: FastMCP,
    profitability_provider: ProfitabilityDataProvider,
    product_client: ProductClient,
    forecast_register_fn: Any | None = None,
) -> None:
    """Enregistre les 4 outils Margin. forecast_register_fn non utilise ici."""

    @mcp.tool(
        name="compute_product_margin",
        description=(
            "Calcule la marge brute d'un produit sur N jours. "
            "Donnees synthetiques (data_origin=synthetic_demo). Decimal pour les calculs."
        ),
    )
    async def compute_product_margin_tool(
        product_id: Annotated[str, Field(description="SKU ou id numerique.")],
        days: Annotated[int, Field(ge=1, le=365)] = 90,
    ) -> dict[str, Any]:
        try:
            pid = await resolve_product_id_cached(product_id, product_client)
        except ResolverError as exc:
            raise to_tool_error(exc) from exc
        try:
            data = await profitability_provider.get_events(days=days)
        except MCPServiceError as exc:
            raise to_tool_error(exc) from exc
        _, names = await _load_products_by_id(product_client)
        margin = compute_product_margin(
            product_id=pid, sales=data.sales, purchases=data.purchases, period_days=days
        )
        d = margin.model_dump(mode="json")
        d["product_name"] = names.get(pid)
        d["data_origin"] = "synthetic_demo"
        return d

    @mcp.tool(
        name="identify_most_profitable",
        description=(
            "Top N produits par metric (gross_margin, gross_margin_rate, sales_volume, "
            "return_on_cost). Donnees synthetiques."
        ),
    )
    async def identify_most_profitable(
        days: Annotated[int, Field(ge=1, le=365)] = 30,
        limit: Annotated[int, Field(ge=1, le=50)] = 10,
        metric: Annotated[str, Field(description="gross_margin|gross_margin_rate|sales_volume|return_on_cost")] = "gross_margin",
    ) -> dict[str, Any]:
        try:
            metric_enum = ProfitabilityMetric(metric)
        except ValueError as exc:
            from ..errors import InvalidInputError

            raise to_tool_error(InvalidInputError(f"Unknown metric: {metric}")) from exc
        try:
            data = await profitability_provider.get_events(days=days)
        except MCPServiceError as exc:
            raise to_tool_error(exc) from exc
        products_by_id, names = await _load_products_by_id(product_client)
        margins = []
        for pid in products_by_id:
            margins.append(
                compute_product_margin(
                    product_id=pid,
                    sales=data.sales,
                    purchases=data.purchases,
                    period_days=days,
                )
            )
        rows = rank_products(margins, metric=metric_enum, limit=limit, names_by_id=names)
        return {
            "metric": metric_enum.value,
            "days": days,
            "limit": limit,
            "products": [r.model_dump(mode="json") for r in rows],
            "data_origin": "synthetic_demo",
        }

    @mcp.tool(
        name="compute_supplier_cost",
        description=(
            "Cout d'achat total par fournisseur (inclut transport) sur N jours. "
            "Donnees synthetiques."
        ),
    )
    async def compute_supplier_cost(
        days: Annotated[int, Field(ge=1, le=365)] = 90,
    ) -> dict[str, Any]:
        try:
            data = await profitability_provider.get_events(days=days)
        except MCPServiceError as exc:
            raise to_tool_error(exc) from exc
        rows = aggregate_supplier_cost(data.purchases, period_days=days)
        return {
            "days": days,
            "suppliers": [r.model_dump(mode="json") for r in rows],
            "data_origin": "synthetic_demo",
        }

    @mcp.tool(
        name="analyze_storage_efficiency",
        description=(
            "Recommandation heuristique par produit (keep/review/reduce/drop_candidate) "
            "croisant marge et complexite de stockage. NON automatique : a valider humainement. "
            "Donnees de marge synthetiques ; complexite reelle."
        ),
    )
    async def analyze_storage_efficiency(
        days: Annotated[int, Field(ge=1, le=365)] = 90,
    ) -> dict[str, Any]:
        try:
            data = await profitability_provider.get_events(days=days)
        except MCPServiceError as exc:
            raise to_tool_error(exc) from exc
        products_by_id, names = await _load_products_by_id(product_client)
        margins = []
        complexity_by_id: dict[int, int] = {}
        for pid, p in products_by_id.items():
            margins.append(
                compute_product_margin(
                    product_id=pid,
                    sales=data.sales,
                    purchases=data.purchases,
                    period_days=days,
                )
            )
            score, _ = assess_complexity(p)
            complexity_by_id[pid] = score
        entries = build_storage_efficiency(margins, complexity_by_id, names)
        return {
            "days": days,
            "products": [e.model_dump(mode="json") for e in entries],
            "data_origin": "synthetic_demo",
            "warning": "Recommandations heuristiques non automatiques ; a valider humainement.",
        }
