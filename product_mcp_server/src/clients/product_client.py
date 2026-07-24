"""Client HTTP vers l'API Produit externe (fournie en Docker).

Encapsule les appels REST vers l'API catalogue.
- Retry simple sur 429/5xx/timeout.
- Mapping strict des erreurs en ProductApiError avec ErrorCode normalise.
- Timeouts explicites (connexion + lecture).
- Aucune stack trace exposee au LLM.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ..errors import InvalidUpstreamResponse, ProductApiError
from ..schemas.common import ErrorCode

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = {429, 502, 503, 504}
DEFAULT_TIMEOUT = 10.0
DEFAULT_MAX_RETRIES = 1


class ProductClient:
    """Client asynchrone vers l'API Produit externe."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._transport = transport

    async def _get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self._base_url}{path}"
        attempt = 0
        last_exc: Exception | None = None
        while attempt <= self._max_retries:
            try:
                async with httpx.AsyncClient(
                    timeout=self._timeout,
                    transport=self._transport,
                ) as client:
                    resp = await client.get(url, params=params)
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_exc = exc
                attempt += 1
                logger.warning("Product API network error on %s (attempt %d)", url, attempt)
                continue

            if resp.status_code in RETRYABLE_STATUS:
                last_exc = ProductApiError(
                    f"Product API {resp.status_code} on {path}",
                    code=ErrorCode.UPSTREAM_UNAVAILABLE,
                    status_code=resp.status_code,
                )
                attempt += 1
                continue

            if resp.status_code == 404:
                raise ProductApiError(
                    "Product not found.",
                    code=ErrorCode.NOT_FOUND,
                    status_code=404,
                )
            if resp.status_code >= 400:
                raise ProductApiError(
                    f"Product API error: HTTP {resp.status_code}",
                    code=ErrorCode.INVALID_UPSTREAM_RESPONSE
                    if resp.status_code in (400, 422)
                    else ErrorCode.UPSTREAM_UNAVAILABLE,
                    status_code=resp.status_code,
                )

            try:
                return resp.json()
            except Exception as exc:
                raise InvalidUpstreamResponse(
                    f"Product API returned invalid JSON: {exc}",
                ) from exc

        if isinstance(last_exc, ProductApiError):
            raise last_exc
        raise ProductApiError(
            "External product API unreachable after retries.",
            code=ErrorCode.UPSTREAM_UNAVAILABLE,
        )

    async def list_products(
        self,
        *,
        category: str | None = None,
        supplier_id: str | None = None,
        include_discontinued: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "limit": max(1, min(limit, 100)),
            "offset": max(0, offset),
            "include_discontinued": str(include_discontinued).lower(),
        }
        if category:
            params["category"] = category
        if supplier_id:
            params["supplier_id"] = supplier_id
        return await self._get_json("/api/v1/products", params=params)

    async def get(self, product_id_or_sku: str) -> dict[str, Any]:
        if not product_id_or_sku:
            raise ProductApiError(
                "Product identifier is required.",
                code=ErrorCode.INVALID_INPUT,
            )
        return await self._get_json(f"/api/v1/products/{product_id_or_sku}")

    async def search(self, query: str, *, limit: int = 10) -> dict[str, Any]:
        if not query or not query.strip():
            raise ProductApiError(
                "Search query must not be empty.",
                code=ErrorCode.INVALID_INPUT,
            )
        params = {"q": query.strip(), "limit": max(1, min(limit, 50))}
        return await self._get_json("/api/v1/products/search", params=params)

    async def list_suppliers(self) -> dict[str, Any]:
        """Liste les fournisseurs (endpoint optionnel de l'API externe)."""
        return await self._get_json("/api/v1/suppliers")
