"""Client HTTP vers l'API Produit externe (fournie en Docker).

Responsabilites :
- Encapsuler les appels REST vers l'API catalogue.
- Mapper les reponses en structures Python (dict) — pas de modele Pydantic
  cote client pour rester agnostique du contenu exact.
- Convertir les erreurs HTTP en ProductApiError.
- Un retry simple sur 5xx et timeout (1 tentative supplementaire).

L'API externe est en lecture seule. Ce client ne fait donc que des GET.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .errors import ProductApiError

logger = logging.getLogger(__name__)


class ProductClient:
    """Client asynchrone vers l'API Produit externe."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 10.0,
        max_retries: int = 1,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        # `transport` est un point d'injection pour les tests (httpx.MockTransport).
        # En production, il reste None et httpx utilise le transport reseau standard.
        self._transport = transport

    async def _get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET avec retry simple (1 fois sur 5xx / ConnectError / TimeoutException)."""
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
                logger.warning(
                    "Product API network error on %s (attempt %d): %s",
                    url,
                    attempt,
                    exc,
                )
                continue

            if 500 <= resp.status_code < 600:
                last_exc = ProductApiError(
                    f"External product API 5xx on {path}: {resp.status_code}",
                    status_code=resp.status_code,
                )
                attempt += 1
                logger.warning(
                    "Product API 5xx on %s (attempt %d): %s",
                    url,
                    attempt,
                    resp.status_code,
                )
                continue

            if resp.status_code == 404:
                raise ProductApiError(
                    "Product not found.",
                    status_code=404,
                )

            if resp.status_code >= 400:
                raise ProductApiError(
                    f"External product API error: HTTP {resp.status_code}",
                    status_code=resp.status_code,
                )

            return resp.json()

        if isinstance(last_exc, ProductApiError):
            raise last_exc
        raise ProductApiError(
            f"External product API unreachable after retries: {last_exc}",
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
        """Liste paginee des produits, avec filtres optionnels.

        Retourne la structure brute de l'API :
        ``{"products": [...], "total": int, "limit": int, "offset": int}``
        (la forme exacte depend de l'API ; on la passe tel quel).
        """
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
        """Recupere un produit par identifiant numerique OU par SKU.

        L'API externe supporte les deux formes dans `/products/{id_or_sku}`.
        """
        if not product_id_or_sku:
            raise ProductApiError("Product identifier is required.", status_code=400)
        return await self._get_json(f"/api/v1/products/{product_id_or_sku}")

    async def search(self, query: str, *, limit: int = 10) -> dict[str, Any]:
        """Recherche textuelle dans le catalogue."""
        if not query or not query.strip():
            raise ProductApiError("Search query must not be empty.", status_code=400)
        params = {"q": query.strip(), "limit": max(1, min(limit, 50))}
        return await self._get_json("/api/v1/products/search", params=params)
