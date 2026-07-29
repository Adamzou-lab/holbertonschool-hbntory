"""Implementation HTTP du ProfitabilityDataProvider.

Endpoint attendu (s'il existe un jour) :

    GET /api/internal/profitability/events?days=180

Reponse :
    { "sales": [...], "purchases": [...] }

Si non disponible, les tools tombent en fixture.
"""

from __future__ import annotations

from typing import Any

import httpx

from ..errors import InvalidUpstreamResponse, StockApiError
from ..schemas.margin import ProfitabilityData

DEFAULT_TIMEOUT = 10.0


class HttpProfitabilityProvider:
    def __init__(
        self,
        base_url: str,
        *,
        internal_token: str,
        timeout_seconds: float = DEFAULT_TIMEOUT,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = internal_token
        self._timeout = timeout_seconds
        self._transport = transport

    async def get_events(
        self,
        *,
        days: int,
        seed: int | None = None,
    ) -> ProfitabilityData:
        url = f"{self._base_url}/api/internal/profitability/events"
        params: dict[str, Any] = {"days": days}
        if seed is not None:
            params["seed"] = seed
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                resp = await client.get(
                    url,
                    params=params,
                    headers={"X-Internal-Token": self._token},
                )
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise StockApiError(f"Profitability events unreachable: {exc}") from exc

        if resp.status_code == 404:
            raise StockApiError(
                "Profitability events endpoint not available on Backoffice.",
                status_code=404,
            )
        if resp.status_code == 403:
            raise StockApiError("Profitability denied (bad token).", status_code=403)
        if resp.status_code >= 400:
            raise StockApiError(
                f"Profitability upstream error: HTTP {resp.status_code}",
                status_code=resp.status_code,
            )
        try:
            return ProfitabilityData.model_validate(resp.json())
        except Exception as exc:
            raise InvalidUpstreamResponse(
                f"Profitability payload malformed: {exc}",
            ) from exc


__all__ = ["HttpProfitabilityProvider"]
