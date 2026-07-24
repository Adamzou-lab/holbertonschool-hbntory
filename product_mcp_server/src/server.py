"""Point d'entree du serveur MCP HBntory.

Serveur FastMCP en transport Streamable HTTP avec :
- 3 outils produit
- 4 outils stock (read-only via API interne Backoffice)
- 10 outils analytics (P1)
- 4 outils forecast (P2)
- 4 outils margin (P3)

Aucun outil n'ecrit dans le stock. Les donnees de rentabilite sont
synthetiques et toujours signalees.

Lancement local : python -m src.server
"""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse

from .clients.product_client import ProductClient
from .clients.stock_client import StockClient
from .config import get_settings
from .providers.forecast_fixture import FixtureForecastProvider
from .providers.profitability_fixture import FixtureProfitabilityProvider
from .schemas.forecast import CalculationBasis
from .tools.analytics_tools import register as register_analytics
from .tools.forecast_tools import register as register_forecast
from .tools.margin_tools import register as register_margin
from .tools.product_tools import register as register_product
from .tools.stock_tools import register as register_stock

logger = logging.getLogger("hbntory.product_mcp")


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def build_server() -> FastMCP:
    """Construit l'instance FastMCP avec tous les outils et providers."""
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

    forecast_provider = FixtureForecastProvider()
    profitability_provider = FixtureProfitabilityProvider()

    mcp = FastMCP(
        name="hbntory-product-mcp",
        stateless_http=True,
        host=settings.mcp_host,
        port=settings.mcp_port,
    )

    register_product(mcp, product_client)
    register_stock(mcp, stock_client, product_client)
    register_analytics(mcp, product_client, stock_client)
    register_forecast(mcp, forecast_provider, product_client, basis=CalculationBasis.FIXTURE_SERIES)
    register_margin(mcp, profitability_provider, product_client)

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
