"""Client HTTP vers l'API interne du Backoffice (lecture stock).

Ce client consomme les routes internes que Nico expose dans `backoffice/app.py` :
  GET  /api/internal/branches
  GET  /api/internal/stock/by-product/<int:product_id>
  GET  /api/internal/stock/by-branch/<int:branch_id>
  POST /api/internal/stock/shopping-list
  GET  /api/internal/health

Auth : header `X-Internal-Token` (env var BACKOFFICE_INTERNAL_TOKEN).
Toutes les requetes passent par ce header — pas de session Flask-Login.

Les `product_id` et `branch_id` envoyes a ce client sont TOUJOURS des entiers
(c'est le MCP qui fait la resolution SKU -> int via resolvers.py avant d'appeler).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .errors import StockApiError

logger = logging.getLogger(__name__)


class StockClient:
    """Client asynchrone vers l'API interne du Backoffice."""

    def __init__(
        self,
        base_url: str,
        *,
        internal_token: str,
        timeout_seconds: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = internal_token
        self._timeout = timeout_seconds
        self._transport = transport

    def _headers(self) -> dict[str, str]:
        return {"X-Internal-Token": self._token}

    async def _get_json(self, path: str) -> Any:
        url = f"{self._base_url}{path}"
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                transport=self._transport,
            ) as client:
                resp = await client.get(url, headers=self._headers())
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise StockApiError(
                f"Internal stock API unreachable: {exc}",
            ) from exc

        return self._parse(resp, path)

    async def _post_json(self, path: str, body: dict[str, Any]) -> Any:
        url = f"{self._base_url}{path}"
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                transport=self._transport,
            ) as client:
                resp = await client.post(url, json=body, headers=self._headers())
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise StockApiError(
                f"Internal stock API unreachable: {exc}",
            ) from exc

        return self._parse(resp, path)

    def _parse(self, resp: httpx.Response, path: str) -> Any:
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 403:
            raise StockApiError(
                "Internal stock API denied request (bad or missing X-Internal-Token).",
                status_code=403,
            )
        if resp.status_code == 404:
            try:
                payload = resp.json()
                msg = payload.get("error") or payload.get("message") or "not found"
            except Exception:
                msg = "not found"
            raise StockApiError(f"{msg}", status_code=404)
        if resp.status_code >= 500:
            raise StockApiError(
                f"Internal stock API 5xx on {path}: {resp.status_code}",
                status_code=resp.status_code,
            )
        raise StockApiError(
            f"Internal stock API error: HTTP {resp.status_code}",
            status_code=resp.status_code,
        )

    # --- Endpoints ---

    async def list_branches(self) -> list[dict[str, Any]]:
        """GET /api/internal/branches -> [{id, name}, ...]"""
        data = await self._get_json("/api/internal/branches")
        if not isinstance(data, list):
            raise StockApiError(
                "Internal stock API returned unexpected payload for /branches "
                f"(expected list, got {type(data).__name__})",
            )
        return data

    async def get_stock_by_product(self, product_id: int) -> list[dict[str, Any]]:
        """GET /api/internal/stock/by-product/<id> -> [{branch_id, branch_name, quantity}]"""
        if not isinstance(product_id, int) or product_id < 1:
            raise StockApiError(f"Invalid product_id: {product_id}", status_code=400)
        return await self._get_json(f"/api/internal/stock/by-product/{product_id}")

    async def get_stock_by_branch(self, branch_id: int) -> list[dict[str, Any]]:
        """GET /api/internal/stock/by-branch/<id> -> [{product_id, quantity}]"""
        if not isinstance(branch_id, int) or branch_id < 1:
            raise StockApiError(f"Invalid branch_id: {branch_id}", status_code=400)
        return await self._get_json(f"/api/internal/stock/by-branch/{branch_id}")

    async def check_shopping_list(
        self,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """POST /api/internal/stock/shopping-list -> reponse agregee."""
        if not items:
            raise StockApiError("items must not be empty", status_code=400)
        return await self._post_json("/api/internal/stock/shopping-list", {"items": items})

    async def health(self) -> dict[str, Any]:
        return await self._get_json("/api/internal/health")
