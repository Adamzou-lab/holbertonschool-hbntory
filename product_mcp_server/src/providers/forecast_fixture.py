"""Implementation fixture du ForecastDataProvider.

Genere une serie temporelle deterministe (seed + sinusoide + bruit) pour
chaque couple (product_id, branch_id). Permet aux outils Forecast de
fonctionner immediatement sans dependre du Backoffice.
"""

from __future__ import annotations

import math
import random
from datetime import UTC, datetime, timedelta

from ..schemas.forecast import StockHistoryPoint

SERIES_VERSION = "fixture_v1"


class FixtureForecastProvider:
    """Genere une serie de stock synthetique deterministe.

    La quantite suit une sinusoide mensuelle + bruit gaussien, clippee a 0.
    Seed = hash(product_id, branch_id, "fixture_v1").
    """

    def __init__(self, *, daily_points: int = 30) -> None:
        self.daily_points = daily_points

    async def get_history(
        self,
        *,
        product_id: int,
        branch_id: int | None,
        days: int,
    ) -> list[StockHistoryPoint]:
        days = max(3, min(days, 365))
        branches = [branch_id] if branch_id is not None else [1, 2]
        all_points: list[StockHistoryPoint] = []
        for bid in branches:
            all_points.extend(self._series(product_id, bid, days))
        all_points.sort(key=lambda p: (p.recorded_at, getattr(p, "_branch_id", 0)))
        return all_points

    def _series(
        self,
        product_id: int,
        branch_id: int,
        days: int,
    ) -> list[StockHistoryPoint]:
        rng = random.Random(f"{product_id}|{branch_id}|{SERIES_VERSION}")
        phase = rng.random() * 2 * math.pi
        amplitude = rng.uniform(5.0, 20.0)
        baseline = rng.uniform(15.0, 60.0)
        now = datetime.now(UTC)
        series: list[StockHistoryPoint] = []
        prev_qty = int(baseline + amplitude * math.sin(phase))
        for i in range(days):
            recorded_at = now - timedelta(days=days - 1 - i)
            target = baseline + amplitude * math.sin(phase + (i / 30.0) * 2 * math.pi)
            noise = rng.gauss(0, 2.5)
            qty = max(0, int(round(target + noise)))
            movement = qty - prev_qty
            series.append(
                StockHistoryPoint(
                    recorded_at=recorded_at,
                    quantity=qty,
                    movement=movement,
                )
            )
            prev_qty = qty
        # Inject branch metadata via private attrs workaround: we attach
        # branch_id on the model_config.extra if needed. Instead we keep
        # branch info at the call site (see forecast_tools).
        for p in series:
            object.__setattr__(p, "_branch_id", branch_id)
        return series


__all__ = ["FixtureForecastProvider", "SERIES_VERSION"]
