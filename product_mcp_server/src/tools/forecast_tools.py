"""Outils MCP Forecast (4 tools, P2).

Tous utilisent un ForecastDataProvider. En l'absence de provider HTTP
(qui depend d'une route Backoffice pas encore livree), les tools
tombent en fixture deterministe.

Resultats limites :
- Qualite "low" -> pas de date de rupture/proc de reorder.
- Mouvement moyen nul -> pas de date.
- Historique insuffisant -> "insufficient_data".
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ..domain.forecasting import (
    best_periodicity,
    estimate_stockout,
    monthly_peaks_and_lows,
    trend_from_history,
)
from ..errors import MCPServiceError, ResolverError, to_tool_error
from ..providers.forecast_base import ForecastDataProvider
from ..resolvers import resolve_product_id_cached
from ..schemas.forecast import (
    CalculationBasis,
    DataQuality,
    StockoutForecast,
    TrendSeries,
)

if TYPE_CHECKING:
    from ..clients.product_client import ProductClient

logger = logging.getLogger(__name__)


def _attach_branch(series: list, branch_id: int, branch_name: str | None) -> list[dict[str, Any]]:
    out = []
    for p in series:
        # StockHistoryPoint has branch_id via setattr (see FixtureForecastProvider).
        bid = getattr(p, "_branch_id", branch_id)
        out.append(
            {
                "branch_id": bid,
                "branch_name": branch_name,
                "recorded_at": p.recorded_at.isoformat(),
                "quantity": p.quantity,
                "movement": p.movement,
            }
        )
    return out


def register(
    mcp: FastMCP,
    forecast_provider: ForecastDataProvider,
    product_client: ProductClient,
    basis: CalculationBasis = CalculationBasis.GENERIC_MOVEMENTS,
) -> None:
    """Enregistre les 4 outils Forecast."""

    @mcp.tool(
        name="get_stock_history",
        description=(
            "Renvoie l'historique de stock d'un produit sur N jours (par branche). "
            "Donnees issues d'un provider (fixture par defaut). "
            "La base de calcul est indiquee explicitement."
        ),
    )
    async def get_stock_history(
        product_id: Annotated[str, Field(description="SKU ou id numerique du produit.")],
        days: Annotated[int, Field(ge=3, le=365)] = 30,
        branch_id: Annotated[int | None, Field(description="Branche specifique (defaut: toutes).")] = None,
    ) -> dict[str, Any]:
        try:
            pid = await resolve_product_id_cached(product_id, product_client)
        except ResolverError as exc:
            raise to_tool_error(exc) from exc
        try:
            points = await forecast_provider.get_history(
                product_id=pid, branch_id=branch_id, days=days
            )
        except MCPServiceError as exc:
            raise to_tool_error(exc) from exc
        series = _attach_branch(points, branch_id or 0, None)
        return {
            "product_id": pid,
            "days": days,
            "calculation_basis": basis.value,
            "history": series,
        }

    @mcp.tool(
        name="analyze_stock_trend",
        description=(
            "Analyse la tendance d'un produit (rising/falling/stable) avec regression lineaire, "
            "R^2 et moyenne mobile 7 jours. Renvoie 'insufficient_data' si < 3 points. "
            "Pas de 'confidence' : on utilise data_quality (low/medium/high)."
        ),
    )
    async def analyze_stock_trend(
        product_id: Annotated[str, Field(description="SKU ou id numerique.")],
        days: Annotated[int, Field(ge=7, le=365)] = 90,
    ) -> dict[str, Any]:
        try:
            pid = await resolve_product_id_cached(product_id, product_client)
        except ResolverError as exc:
            raise to_tool_error(exc) from exc
        try:
            points = await forecast_provider.get_history(product_id=pid, branch_id=None, days=days)
        except MCPServiceError as exc:
            raise to_tool_error(exc) from exc
        # Agrege toutes branches pour la tendance globale.
        direction, slope, r2, ma7, quality = trend_from_history(points)
        by_branch: list[dict[str, Any]] = []
        # Si le provider expose _branch_id on peut regrouper :
        by_id: dict[int, list] = {}
        for p in points:
            bid = getattr(p, "_branch_id", 0)
            by_id.setdefault(bid, []).append(p)
        for bid, pts in by_id.items():
            d, s, r, m, q = trend_from_history(pts)
            by_branch.append(
                TrendSeries(
                    branch_id=bid,
                    branch_name=None,
                    direction=d,
                    avg_daily_change=s,
                    r_squared=r,
                    moving_average_7d=m,
                    data_quality=q,
                ).model_dump()
            )
        return {
            "product_id": pid,
            "days": days,
            "global": {
                "direction": direction.value,
                "avg_daily_change": slope,
                "r_squared": r2,
                "moving_average_7d": ma7,
                "data_quality": quality.value,
            },
            "by_branch": by_branch,
            "calculation_basis": basis.value,
        }

    @mcp.tool(
        name="forecast_stockout_and_reorder",
        description=(
            "Estime la date de rupture et la date de commande recommandee pour un produit "
            "sur une branche. Renvoie None si qualite trop faible ou mouvement moyen nul. "
            "Inclut hypotheses et limitations."
        ),
    )
    async def forecast_stockout_and_reorder(
        product_id: Annotated[str, Field(description="SKU ou id numerique.")],
        branch_id: Annotated[int, Field(description="Branche cible.")],
        safety_buffer_days: Annotated[int, Field(ge=0, le=60)] = 7,
        days: Annotated[int, Field(ge=7, le=365)] = 90,
    ) -> dict[str, Any]:
        try:
            pid = await resolve_product_id_cached(product_id, product_client)
        except ResolverError as exc:
            raise to_tool_error(exc) from exc
        try:
            points = await forecast_provider.get_history(
                product_id=pid, branch_id=branch_id, days=days
            )
        except MCPServiceError as exc:
            raise to_tool_error(exc) from exc
        direction, slope, r2, ma7, quality = trend_from_history(points)
        current = points[-1].quantity if points else 0
        last_dt = points[-1].recorded_at if points else datetime.now(UTC)
        # avg_daily_movement : on utilise la pente de regression si negative.
        avg_daily_movement = -slope if slope < 0 else 0.0
        stockout_date, reorder_date, hypotheses, limitations = estimate_stockout(
            current_quantity=current,
            avg_daily_movement=avg_daily_movement,
            safety_buffer_days=safety_buffer_days,
            last_date=last_dt,
            quality=quality,
        )
        out = StockoutForecast(
            product_id=pid,
            branch_id=branch_id,
            current_quantity=current,
            avg_daily_movement=avg_daily_movement if avg_daily_movement > 0 else None,
            safety_buffer_days=safety_buffer_days,
            estimated_stockout_date=stockout_date,
            recommended_reorder_date=reorder_date,
            hypotheses=hypotheses,
            limitations=limitations,
            data_quality=quality,
        )
        return out.model_dump(mode="json")

    @mcp.tool(
        name="detect_seasonal_pattern",
        description=(
            "Cherche un pattern saisonnier sur un produit via autocorr (periodes 7, 30, 90 j). "
            "Necessite >= 2 cycles complets. Renvoie 'insufficient_data' sinon. "
            "N'utilise PAS une simple regression lineaire."
        ),
    )
    async def detect_seasonal_pattern(
        product_id: Annotated[str, Field(description="SKU ou id numerique.")],
        days: Annotated[int, Field(ge=90, le=730)] = 365,
    ) -> dict[str, Any]:
        try:
            pid = await resolve_product_id_cached(product_id, product_client)
        except ResolverError as exc:
            raise to_tool_error(exc) from exc
        try:
            points = await forecast_provider.get_history(product_id=pid, branch_id=None, days=days)
        except MCPServiceError as exc:
            raise to_tool_error(exc) from exc
        if len(points) < 14:
            return {
                "product_id": pid,
                "has_pattern": False,
                "cycles_completed": 0,
                "data_quality": DataQuality.LOW.value,
                "limitations": ["insufficient_data (< 14 points)"],
            }
        values = [float(p.quantity) for p in points]
        best_lag, best_score, cycles = best_periodicity(values, candidate_periods=[7, 30, 90])
        # Peaks/lows par mois a partir des timestamps
        monthly: dict[int, list[float]] = {}
        for p in points:
            monthly.setdefault(p.recorded_at.month, []).append(float(p.quantity))
        peak_months, low_months = monthly_peaks_and_lows(monthly)
        quality = (
            DataQuality.HIGH
            if cycles >= 4
            else DataQuality.MEDIUM
            if cycles >= 2
            else DataQuality.LOW
        )
        return {
            "product_id": pid,
            "has_pattern": best_lag is not None and best_score > 0.2,
            "best_period_days": best_lag,
            "autocorrelation_at_best_lag": best_score,
            "cycles_completed": cycles,
            "peak_months": peak_months,
            "low_months": low_months,
            "data_quality": quality.value,
            "candidate_periods_days": [7, 30, 90],
            "calculation_basis": basis.value,
            "limitations": [] if quality is not DataQuality.LOW else ["insufficient_data"],
        }
