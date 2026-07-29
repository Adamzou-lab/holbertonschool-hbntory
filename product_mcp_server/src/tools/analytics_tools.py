"""Outils MCP Analytics (10 tools, P1).

Couverture :
- Agrégation catalogue (1)
- Extrêmes (2)
- Fournisseurs (1)
- Valeur stock (1)
- Complexité stockage (1)
- Discontinued (1)
- Distribution stock (1)
- Over/understock (2)

Tous les outils sont read-only. Ils utilisent les clients HTTP et le
cache local TTL (CATALOG_CACHE, SUPPLIERS_CACHE).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ..clients.product_client import ProductClient
from ..clients.stock_client import StockClient
from ..domain.cache import CATALOG_CACHE, SUPPLIERS_CACHE
from ..domain.catalog_analytics import (
    aggregate_by_category,
    aggregate_suppliers,
    estimate_inventory_value,
    extreme_prices,
    extreme_weights,
)
from ..domain.pagination import DEFAULT_PAGE_SIZE, paginate_all
from ..errors import MCPServiceError, to_tool_error

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


async def _load_full_catalog(product_client: ProductClient) -> tuple[list[dict[str, Any]], bool]:
    """Renvoie (products, served_stale)."""

    async def compute() -> list[dict[str, Any]]:
        return await paginate_all(
            lambda offset, limit: product_client.list_products(offset=offset, limit=limit),
            page_size=DEFAULT_PAGE_SIZE,
            # L'API Produit externe renvoie la liste sous "results", pas
            # "products" (vérifié contre la vraie API : {"count", "results",
            # "limit", "offset"}) — avec la mauvaise clé ce catalogue était
            # systématiquement vide, silencieusement (aucune erreur levée).
            results_key="results",
        )

    value, stale = await CATALOG_CACHE.get_or_compute("catalog:full", compute)
    return value, stale


async def _load_suppliers(product_client: ProductClient) -> tuple[dict[str, dict[str, Any]], bool]:
    async def compute() -> dict[str, dict[str, Any]]:
        try:
            payload = await product_client.list_suppliers()
        except MCPServiceError:
            return {}
        # Même remarque que _load_full_catalog : la clé réelle est
        # "results", pas "suppliers". L'ancien fallback `payload.get(
        # "suppliers", payload)` retombait sur le dict entier (count/
        # results/limit/offset), puis itérait sur ses clés (des strings)
        # au lieu des objets fournisseur -> AttributeError au premier
        # `s.get("id")`. Confirmé en le déclenchant en direct avant fix.
        sup_list = payload.get("results", []) if isinstance(payload, dict) else payload
        out: dict[str, dict[str, Any]] = {}
        for s in sup_list or []:
            out[s.get("id")] = s
        return out

    value, stale = await SUPPLIERS_CACHE.get_or_compute("suppliers:full", compute)
    return value, stale


async def _stock_summary(
    stock_client: StockClient,
    branches: list[dict[str, Any]],
) -> tuple[
    dict[int, int],
    dict[int, dict[int, int]],
]:
    """Renvoie (total_per_product, per_branch_per_product)."""
    total: dict[int, int] = {}
    pb: dict[int, dict[int, int]] = {}
    for b in branches:
        rows = await stock_client.get_stock_by_branch(b["id"])
        for r in rows:
            pid = r.get("product_id")
            qty = int(r.get("quantity", 0))
            if qty <= 0:
                continue
            total[pid] = total.get(pid, 0) + qty
            pb.setdefault(pid, {})[b["id"]] = qty
    return total, pb


def register(mcp: FastMCP, product_client: ProductClient, stock_client: StockClient) -> None:
    """Enregistre les 10 outils Analytics sur l'instance FastMCP."""

    @mcp.tool(
        name="analyze_catalog_by_category",
        description=(
            "Agrege le catalogue par categorie : nombre de produits, prix moyen/min/max, "
            "poids total, taux de valeurs manquantes. Aucune valeur None n'est transformee en zero."
        ),
    )
    async def analyze_catalog_by_category() -> dict[str, Any]:
        try:
            products, stale = await _load_full_catalog(product_client)
        except MCPServiceError as exc:
            raise to_tool_error(exc) from exc
        cats = aggregate_by_category(products)
        return {
            "categories": cats,
            "products_analyzed": len(products),
            "warning": "result is at catalog price, not purchase cost" + (" (cache stale)" if stale else ""),
        }

    @mcp.tool(
        name="find_extreme_prices",
        description=(
            "Renvoie le top N produits les plus chers ou les moins chers. "
            "Filtrage optionnel par categorie. Les produits sans prix sont exclus."
        ),
    )
    async def find_extreme_prices(
        direction: Annotated[str, Field(description="'highest' ou 'lowest'.")] = "highest",
        limit: Annotated[int, Field(ge=1, le=20)] = 5,
        category: Annotated[str | None, Field(description="Categorie exacte (optionnel).")] = None,
    ) -> dict[str, Any]:
        if direction not in ("highest", "lowest"):
            from ..errors import InvalidInputError

            raise to_tool_error(InvalidInputError("direction must be 'highest' or 'lowest'"))
        try:
            products, _ = await _load_full_catalog(product_client)
        except MCPServiceError as exc:
            raise to_tool_error(exc) from exc
        rows = extreme_prices(products, direction, limit, category=category)
        return {
            "direction": direction,
            "limit": limit,
            "category": category,
            "products": rows,
        }

    @mcp.tool(
        name="find_extreme_weights",
        description=(
            "Renvoie le top N produits les plus lourds / legers. "
            "Les produits sans poids sont exclus et leur nombre est signale."
        ),
    )
    async def find_extreme_weights(
        direction: Annotated[str, Field(description="'heaviest' ou 'lightest'.")] = "heaviest",
        limit: Annotated[int, Field(ge=1, le=20)] = 5,
    ) -> dict[str, Any]:
        if direction not in ("heaviest", "lightest"):
            from ..errors import InvalidInputError

            raise to_tool_error(InvalidInputError("direction must be 'heaviest' or 'lightest'"))
        try:
            products, _ = await _load_full_catalog(product_client)
        except MCPServiceError as exc:
            raise to_tool_error(exc) from exc
        rows, missing = extreme_weights(products, direction, limit)
        return {
            "direction": direction,
            "limit": limit,
            "products": rows,
            "missing_weight_count": missing,
            "warning": f"{missing} produits sans poids ont ete exclus du classement.",
        }

    @mcp.tool(
        name="analyze_supplier_portfolio",
        description=(
            "Vue par fournisseur : nombre de produits, categories couvertes, prix moyen, "
            "delai (lead time) et score de fiabilite. Pas de jugement qualite automatique."
        ),
    )
    async def analyze_supplier_portfolio() -> dict[str, Any]:
        try:
            products, _ = await _load_full_catalog(product_client)
            suppliers, _ = await _load_suppliers(product_client)
        except MCPServiceError as exc:
            raise to_tool_error(exc) from exc
        rows = aggregate_suppliers(products, suppliers)
        return {"suppliers": rows, "suppliers_with_full_metadata": len(suppliers)}

    @mcp.tool(
        name="estimate_catalog_stock_value",
        description=(
            "Estimation de la valeur du stock au prix catalogue (unit_price x quantite). "
            "Ce n'est PAS un cout d'achat ni une marge. Repartition par categorie et par branche."
        ),
    )
    async def estimate_catalog_stock_value() -> dict[str, Any]:
        try:
            products, _ = await _load_full_catalog(product_client)
            branches = await stock_client.list_branches()
            total, pb = await _stock_summary(stock_client, branches)
        except MCPServiceError as exc:
            raise to_tool_error(exc) from exc
        result = estimate_inventory_value(products, total, branches, stock_by_product_branch=pb)
        return result

    @mcp.tool(
        name="assess_storage_complexity",
        description=(
            "Score heuristique (0..100) par produit, base sur poids, categorie, statut "
            "discontinue et tags. Methodologie = heuristic_v1."
        ),
    )
    async def assess_storage_complexity(
        limit: Annotated[int, Field(ge=1, le=100)] = 20,
    ) -> dict[str, Any]:
        from ..domain.storage_complexity import METHODOLOGY, assess_complexity

        try:
            products, _ = await _load_full_catalog(product_client)
        except MCPServiceError as exc:
            raise to_tool_error(exc) from exc
        scored = []
        for p in products:
            score, factors = assess_complexity(p)
            scored.append(
                {
                    "sku": p.get("sku"),
                    "name": p.get("name"),
                    "weight_kg": p.get("weight_kg"),
                    "category": p.get("category"),
                    "complexity_score": score,
                    "factors": factors,
                }
            )
        scored.sort(key=lambda x: x["complexity_score"], reverse=True)
        return {"methodology": METHODOLOGY, "products": scored[:limit]}

    @mcp.tool(
        name="find_discontinued_with_stock",
        description=(
            "Liste les produits marques discontinued qui ont encore du stock. "
            "Le tool signale 'review_required=True' mais ne decide pas d'une liquidation."
        ),
    )
    async def find_discontinued_with_stock() -> dict[str, Any]:
        try:
            products, _ = await _load_full_catalog(product_client)
            branches = await stock_client.list_branches()
            total, pb = await _stock_summary(stock_client, branches)
        except MCPServiceError as exc:
            raise to_tool_error(exc) from exc
        products_by_id = {p.get("id"): p for p in products if p.get("id") is not None}
        out = []
        for pid, qty in total.items():
            p = products_by_id.get(pid)
            if not p or not p.get("discontinued"):
                continue
            out.append(
                {
                    "sku": p.get("sku"),
                    "name": p.get("name"),
                    "category": p.get("category"),
                    "total_stock": qty,
                    "branches": [
                        {"branch_id": bid, "quantity": q}
                        for bid, q in pb.get(pid, {}).items()
                    ],
                    "review_required": True,
                }
            )
        out.sort(key=lambda x: x["total_stock"], reverse=True)
        return {"products": out}

    @mcp.tool(
        name="analyze_stock_distribution",
        description=(
            "Repartition du stock par branche, top categories par branche, et indice de "
            "concentration (Gini + part de la branche majoritaire)."
        ),
    )
    async def analyze_stock_distribution() -> dict[str, Any]:
        from ..domain.stock_analytics import stock_distribution

        try:
            products, _ = await _load_full_catalog(product_client)
            branches = await stock_client.list_branches()
            _, pb = await _stock_summary(stock_client, branches)
        except MCPServiceError as exc:
            raise to_tool_error(exc) from exc
        products_by_id = {p.get("id"): p for p in products if p.get("id") is not None}
        return stock_distribution(pb, branches, products_by_id)

    @mcp.tool(
        name="find_overstocked_products",
        description=(
            "Produits dont le stock total depasse le seuil absolu specifie. "
            "Methode simple (quantite), pas une prevision de demande."
        ),
    )
    async def find_overstocked_products(
        threshold_units: Annotated[int, Field(ge=1)] = 50,
        limit: Annotated[int, Field(ge=1, le=50)] = 10,
    ) -> dict[str, Any]:
        from ..domain.stock_analytics import find_overstocked

        try:
            branches = await stock_client.list_branches()
            _, pb = await _stock_summary(stock_client, branches)
        except MCPServiceError as exc:
            raise to_tool_error(exc) from exc
        rows = find_overstocked(pb, threshold_units, limit)
        return {
            "threshold_units": threshold_units,
            "method": "absolute_quantity_threshold",
            "products": rows,
        }

    @mcp.tool(
        name="find_understocked_products",
        description=(
            "Produits dont le stock total est sous le seuil. "
            "Methode simple (quantite), pas une prevision de demande."
        ),
    )
    async def find_understocked_products(
        threshold_units: Annotated[int, Field(ge=0)] = 5,
        limit: Annotated[int, Field(ge=1, le=50)] = 10,
        category: Annotated[str | None, Field(description="Filtre categorie (optionnel).")] = None,
    ) -> dict[str, Any]:
        from ..domain.stock_analytics import find_understocked

        try:
            products, _ = await _load_full_catalog(product_client)
            branches = await stock_client.list_branches()
            _, pb = await _stock_summary(stock_client, branches)
        except MCPServiceError as exc:
            raise to_tool_error(exc) from exc
        products_by_id = {p.get("id"): p for p in products if p.get("id") is not None}
        rows = find_understocked(pb, threshold_units, limit, category, products_by_id)
        return {
            "threshold_units": threshold_units,
            "category": category,
            "method": "absolute_quantity_threshold",
            "products": rows,
        }
