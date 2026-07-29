"""Interfaces providers pour Phase 2 (forecast) et Phase 3 (profitabilite).

L'objectif est de detacher les tools de l'implementation reelle des sources
de donnees : on peut developper et tester avec des fixtures, basculer sur
HTTP quand une source compatible est disponible.
"""

from __future__ import annotations

from typing import Protocol

from ..schemas.forecast import StockHistoryPoint


class ForecastDataProvider(Protocol):
    """Interface pour une source d'historique de stock.

    Une implementation peut etre :
    - FixtureForecastProvider : donnees generees localement.
    - HttpForecastProvider : appels HTTP vers une route compatible (si elle existe).
    """

    async def get_history(
        self,
        *,
        product_id: int,
        branch_id: int | None,
        days: int,
    ) -> list[StockHistoryPoint]:
        """Renvoie une serie de points (ordered chronologically)."""
        ...


__all__ = ["ForecastDataProvider"]
