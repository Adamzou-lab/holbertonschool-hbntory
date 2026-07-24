"""Client HTTP vers l'API interne du Backoffice HBntory (lecture stock)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ..errors import InvalidUpstreamResponse, StockApiError
from ..schemas.common import ErrorCode

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = {429, 502, 503, 504}
DEFAULT_TIMEOUT = 10.0
DEFAULT_MAX_RETRIES = 1


class StockClient:
    def __init__(
        self,
        base_url: str,
        *,
        internal_token: str,
        timeout_seconds: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = internal_token
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._transport = transport

    def _headers(self) -> dict[str, str]:
        return {"X-Internal-Token": self._token}

    async def _get_json(self, path: str) -> Any:
        url = f"{self._base_url}{path}"
        attempt = 0
        last_exc: Exception | None = None
        while attempt <= self._max_retries:
            try:
                async with httpx.AsyncClient(
                    timeout=self._timeout,
                    transport=self._transport,
                ) as client:
                    resp = await client.get(url, headers=self._headers())
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_exc = exc
                attempt += 1
                logger.warning("Stock API network error on %s (attempt %d)", url, attempt)
                continue

            if resp.status_code in RETRYABLE_STATUS:
                last_exc = StockApiError(
                    f"Stock API {resp.status_code} on {path}",
                    code=ErrorCode.UPSTREAM_UNAVAILABLE,
                    status_code=resp.status_code,
                )
                attempt += 1
                continue

            if resp.status_code == 403:
                raise StockApiError(
                    "Internal stock API denied request (bad or missing X-Internal-Token).",
                    code=ErrorCode.UNAUTHORIZED,
                    status_code=403,
                )
            if resp.status_code == 404:
                raise StockApiError(
                    "Not found.",
                    code=ErrorCode.NOT_FOUND,
                    status_code=404,
                )
            if resp.status_code >= 400:
                raise StockApiError(
                    f"Internal stock API error: HTTP {resp.status_code}",
                    code=ErrorCode.UPSTREAM_UNAVAILABLE,
                    status_code=resp.status_code,
                )

            try:
                return resp.json()
            except Exception as exc:
                raise InvalidUpstreamResponse(
                    f"Stock API returned invalid JSON: {exc}",
                ) from exc

        if isinstance(last_exc, StockApiError):
            raise last_exc
        raise StockApiError(
            "Internal stock API unreachable after retries.",
            code=ErrorCode.UPSTREAM_UNAVAILABLE,
        )

    async def _post_json(self, path: str, body: dict[str, Any]) -> Any:
        url = f"{self._base_url}{path}"
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                resp = await client.post(url, json=body, headers=self._headers())
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise StockApiError(
                f"Internal stock API unreachable: {exc}",
                code=ErrorCode.UPSTREAM_UNAVAILABLE,
            ) from exc

        if resp.status_code == 404:
            raise StockApiError(
                "Not found.",
                code=ErrorCode.NOT_FOUND,
                status_code=404,
            )
        if resp.status_code >= 400:
            raise StockApiError(
                f"Stock API error: HTTP {resp.status_code}",
                code=ErrorCode.UPSTREAM_UNAVAILABLE,
                status_code=resp.status_code,
            )
        try:
            return resp.json()
        except Exception as exc:
            raise InvalidUpstreamResponse(f"Stock API invalid JSON: {exc}") from exc

    async def list_branches(self) -> list[dict[str, Any]]:
        return await self._get_json("/api/internal/branches")

    async def get_stock_by_product(self, product_id: int) -> list[dict[str, Any]]:
        return await self._get_json(f"/api/internal/stock/by-product/{product_id}")

    async def get_stock_by_branch(self, branch_id: int) -> list[dict[str, Any]]:
        return await self._get_json(f"/api/internal/stock/by-branch/{branch_id}")

    async def check_shopping_list(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        return await self._post_json("/api/internal/stock/shopping-list", {"items": items})
