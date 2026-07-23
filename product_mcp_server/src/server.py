"""Point d'entree du serveur MCP HBntory Produit.

Lance un FastMCP en transport Streamable HTTP. Les outils produit
(list/get/search) sont enregistres ici. Les outils stock seront ajoutes
quand Nico livrera l'API interne du Backoffice (cf. stock_client.py,
stock_tools.py).

Usage local :
    cd product_mcp_server
    python -m src.server

Tests :
    pytest -v
"""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse

from .config import get_settings
from .product_client import ProductClient
from .stock_client import StockClient
from .tools.product_tools import register as register_product_tools
from .tools.stock_tools import register as register_stock_tools

logger = logging.getLogger("hbntory.product_mcp")


def _configure_logging(level: str) -> None:
    """Configure le logging racine une seule fois."""
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def build_server() -> FastMCP:
    """Construit l'instance FastMCP avec les outils connus.

    Separe de main() pour faciliter les tests d'integration.
    """
    settings = get_settings()
    _configure_logging(settings.log_level)

    product_client = ProductClient(
        base_url=settings.products_api_base_url,
        timeout_seconds=settings.request_timeout_seconds,
    )
    stock_client = StockClient(
        base_url=settings.backoffice_base_url,
        internal_token=settings.backoffice_internal_token,
        timeout_seconds=settings.request_timeout_seconds,
    )

    mcp = FastMCP(
        name="hbntory-product-mcp",
        stateless_http=True,
        host=settings.mcp_host,
        port=settings.mcp_port,
    )

    register_product_tools(mcp, product_client)
    register_stock_tools(mcp, stock_client, product_client)

    @mcp.custom_route("/health", methods=["GET"])
    async def health(_request) -> JSONResponse:
        return JSONResponse({"status": "ok", "service": "hbntory-product-mcp"})

    return mcp


def main() -> None:
    settings = get_settings()
    mcp = build_server()
    logger.info(
        "Starting hbntory-product-mcp on %s:%d (products=%s, backoffice=%s)",
        settings.mcp_host,
        settings.mcp_port,
        settings.products_api_base_url,
        settings.backoffice_base_url,
    )
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
