"""Tools MCP lies au catalogue produit (via API externe).

Trois outils exposes :
  - list_products    : liste paginee + filtres
  - get_product      : detail d'un produit (par SKU ou id)
  - search_products  : recherche textuelle

Chaque tool est un wrapper async qui appelle ProductClient et mappe
les erreurs metier en ToolError via errors.to_tool_error.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ..errors import MCPServiceError, to_tool_error

if TYPE_CHECKING:
    from ..product_client import ProductClient

logger = logging.getLogger(__name__)


def register(mcp: FastMCP, product_client: ProductClient) -> None:
    """Enregistre les 3 outils produit sur l'instance FastMCP."""

    @mcp.tool(
        name="list_products",
        description=(
            "Liste paginee des produits du catalogue externe. "
            "Filtres optionnels : categorie, fournisseur, inclusion des "
            "produits arretes, pagination (limit 1..100, offset >= 0). "
            "Ne renvoie PAS d'info de stock (le stock est gere par "
            "d'autres outils)."
        ),
    )
    async def list_products(
        category: Annotated[
            str | None,
            Field(description="Filtre exact sur la categorie (ex: 'Accessories')."),
        ] = None,
        supplier_id: Annotated[
            str | None,
            Field(description="Filtre exact sur le supplier_id (ex: 'SUP-HBT-001')."),
        ] = None,
        include_discontinued: Annotated[
            bool,
            Field(description="Inclure les produits marques discontinued. Defaut: false."),
        ] = False,
        limit: Annotated[
            int,
            Field(ge=1, le=100, description="Taille de page (1..100). Defaut: 20."),
        ] = 20,
        offset: Annotated[
            int,
            Field(ge=0, description="Decalage de pagination (>= 0). Defaut: 0."),
        ] = 0,
    ) -> dict[str, Any]:
        try:
            return await product_client.list_products(
                category=category,
                supplier_id=supplier_id,
                include_discontinued=include_discontinued,
                limit=limit,
                offset=offset,
            )
        except MCPServiceError as exc:
            logger.warning("list_products failed: %s", exc)
            raise to_tool_error(exc) from exc

    @mcp.tool(
        name="get_product",
        description=(
            "Renvoie le detail complet d'un produit (nom, description, "
            "prix, categorie, fournisseur, tags, etc.). "
            "Accepte un identifiant numerique ('1') OU un SKU ('HB-LAP-1001'). "
            "Si l'identifiant n'existe pas, l'outil renvoie une erreur claire."
        ),
    )
    async def get_product(
        product_id: Annotated[
            str,
            Field(
                description=(
                    "Identifiant produit. Accepte un id numerique ('1') ou un SKU "
                    "commencant par 'HB-' (ex: 'HB-LAP-1001')."
                ),
            ),
        ],
    ) -> dict[str, Any]:
        try:
            return await product_client.get(product_id)
        except MCPServiceError as exc:
            logger.warning("get_product(%s) failed: %s", product_id, exc)
            raise to_tool_error(exc) from exc

    @mcp.tool(
        name="search_products",
        description=(
            "Recherche textuelle dans le catalogue (nom, SKU, description, tags). "
            "Query non vide. Renvoie au plus `limit` produits."
        ),
    )
    async def search_products(
        query: Annotated[
            str,
            Field(min_length=1, description="Texte cherche (non vide)."),
        ],
        limit: Annotated[
            int,
            Field(ge=1, le=50, description="Nombre max de resultats (1..50). Defaut: 10."),
        ] = 10,
    ) -> dict[str, Any]:
        try:
            return await product_client.search(query, limit=limit)
        except MCPServiceError as exc:
            logger.warning("search_products(%r) failed: %s", query, exc)
            raise to_tool_error(exc) from exc
