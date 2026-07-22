"""Tools MCP lies au stock HBntory (lecture seule via Backoffice interne).

Quatre outils exposes :
  - list_branches              : liste des branches (id, name)
  - get_product_availability   : ou trouve-t-on un produit (toutes branches)
  - get_branch_inventory       : contenu d'une branche (produits + quantites)
  - check_shopping_list        : meilleure(s) branche(s) pour une liste d'achat

Tous ces outils sont READ-ONLY. Aucune mutation de stock n'est possible
via MCP : les add/remove restent dans le Backoffice, derriere auth + role.

Les `product_id` recus en string sont resolus en int via le resolver
avant d'appeler l'API interne (coherent avec la DB du Backoffice).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Annotated, Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import Field

from ..errors import MCPServiceError, ResolverError, to_tool_error
from ..resolvers import resolve_product_id_cached

if TYPE_CHECKING:
    from ..product_client import ProductClient
    from ..stock_client import StockClient

logger = logging.getLogger(__name__)


async def _resolve_input_product_id(
    raw: str,
    product_client: ProductClient,
) -> int:
    """Convertit le product_id texte de l'agent en int exploitable."""
    try:
        return await resolve_product_id_cached(raw, product_client)
    except ResolverError as exc:
        raise ToolError(str(exc)) from exc
    except MCPServiceError as exc:
        raise to_tool_error(exc) from exc


def register(
    mcp: FastMCP,
    stock_client: StockClient,
    product_client: ProductClient,
) -> None:
    """Enregistre les 4 outils stock sur l'instance FastMCP."""

    @mcp.tool(
        name="list_branches",
        description=(
            "Liste les branches HBntory connues (id + nom). "
            "A appeler en premier pour pouvoir designer une branche "
            "par son nom humain dans les autres outils."
        ),
    )
    async def list_branches() -> dict[str, Any]:
        try:
            branches = await stock_client.list_branches()
        except MCPServiceError as exc:
            logger.warning("list_branches failed: %s", exc)
            raise to_tool_error(exc) from exc
        return {"branches": branches}

    @mcp.tool(
        name="get_product_availability",
        description=(
            "Indique dans quelle(s) branche(s) un produit est disponible, "
            "avec la quantite par branche. "
            "Accepte un id numerique ('1') ou un SKU ('HB-LAP-1001'). "
            "Si le produit n'existe pas dans le catalogue, renvoie une erreur."
        ),
    )
    async def get_product_availability(
        product_id: Annotated[
            str,
            Field(
                description=(
                    "Identifiant produit. Accepte '1' (id numerique) ou 'HB-LAP-1001' (SKU)."
                ),
            ),
        ],
    ) -> dict[str, Any]:
        pid_int = await _resolve_input_product_id(product_id, product_client)
        try:
            rows = await stock_client.get_stock_by_product(pid_int)
        except MCPServiceError as exc:
            logger.warning("get_product_availability(%s) failed: %s", product_id, exc)
            raise to_tool_error(exc) from exc
        total = sum(int(r.get("quantity", 0)) for r in rows)
        return {"product_id": pid_int, "branches": rows, "total": total}

    @mcp.tool(
        name="get_branch_inventory",
        description=(
            "Liste les produits actuellement en stock dans une branche, "
            "avec leur quantite. Renvoie juste les product_id (le detail "
            "produit s'obtient via get_product)."
        ),
    )
    async def get_branch_inventory(
        branch_id: Annotated[
            int,
            Field(ge=1, description="Identifiant numerique de la branche (cf. list_branches)."),
        ],
    ) -> dict[str, Any]:
        try:
            rows = await stock_client.get_stock_by_branch(branch_id)
        except MCPServiceError as exc:
            logger.warning("get_branch_inventory(%s) failed: %s", branch_id, exc)
            raise to_tool_error(exc) from exc
        return {
            "branch_id": branch_id,
            "items": rows,
            "total_items": len(rows),
        }

    @mcp.tool(
        name="check_shopping_list",
        description=(
            "Pour une liste d'achat (product_id + quantite), indique "
            "quelle(s) branche(s) la satisfait le mieux. Renvoie, pour "
            "chaque branche, le detail de ce qui est satisfait / manquant, "
            "et la quantite manquante cumulee."
            "Accepte les product_id sous forme numerique ('1') ou SKU ('HB-LAP-1001')."
        ),
    )
    async def check_shopping_list(
        items: Annotated[
            list[dict[str, Any]],
            Field(
                description=(
                    "Liste d'achat. Chaque item : "
                    "{'product_id': str, 'quantity': int >= 1}. "
                    "1 a 50 items."
                ),
                min_length=1,
                max_length=50,
            ),
        ],
    ) -> dict[str, Any]:
        if not items:
            raise ToolError("items must not be empty")
        if len(items) > 50:
            raise ToolError("items must contain at most 50 entries")

        # Validation Pydantic additionnelle (quantity >= 1)
        for idx, item in enumerate(items):
            qty = item.get("quantity")
            if not isinstance(qty, int) or qty < 1:
                raise ToolError(f"items[{idx}].quantity must be a positive integer")
            if "product_id" not in item or not str(item["product_id"]).strip():
                raise ToolError(f"items[{idx}].product_id is required")

        # Resolution des product_id en int
        resolved: list[dict[str, Any]] = []
        for item in items:
            pid_int = await _resolve_input_product_id(str(item["product_id"]), product_client)
            resolved.append({"product_id": pid_int, "quantity": int(item["quantity"])})

        try:
            result = await stock_client.check_shopping_list(resolved)
        except MCPServiceError as exc:
            logger.warning("check_shopping_list failed: %s", exc)
            raise to_tool_error(exc) from exc
        return result
