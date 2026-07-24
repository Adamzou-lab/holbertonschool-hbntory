"""Implementation HTTP du ForecastDataProvider.

Endpoint attendu (s'il existe un jour) :

    GET /api/internal/forecast/history?product_id=...&branch_id=...&days=...

Reponse JSON :
    { "history": [ {branch_id, branch_name, recorded_at, quantity, movement}, ... ] }

Si la route n'existe pas, le tool doit tomber en fallback fixture.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ..errors import InvalidUpstreamResponse, StockApiError
from ..schemas.forecast import StockHistoryPoint

logger = logging.getLogger(__name__)


class HttpForecastProvider:
    """Implementation HTTP du ForecastDataProvider.

    Sans contrat ferme cote Backoffice, cette implementation est configurable
    et leve une erreur claire si la route n'est pas disponible. Les tools
    doivent basculer sur la fixture plutot que d'echouer.
    """

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

    async def get_history(
        self,
        *,
        product_id: int,
        branch_id: int | None,
        days: int,
    ) -> list[StockHistoryPoint]:
        url = f"{self._base_url}/api/internal/forecast/history"
        params: dict[str, Any] = {"product_id": product_id, "days": days}
        if branch_id is not None:
            params["branch_id"] = branch_id
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
            raise StockApiError(
                f"Forecast history endpoint unreachable: {exc}",
            ) from exc

        if resp.status_code == 404:
            raise StockApiError(
                "Forecast history endpoint not available on Backoffice.",
                status_code=404,
            )
        if resp.status_code == 403:
            raise StockApiError("Forecast history denied (bad token).", status_code=403)
        if resp.status_code >= 400:
            raise StockApiError(
                f"Forecast history upstream error: HTTP {resp.status_code}",
                status_code=resp.status_code,
            )

        try:
            payload = resp.json()
            raw_points = payload.get("history", [])
            return [StockHistoryPoint.model_validate(p) for p in raw_points]
        except Exception as exc:
            raise InvalidUpstreamResponse(
                f"Forecast history payload malformed: {exc}",
            ) from exc


__all__ = ["HttpForecastProvider"]
