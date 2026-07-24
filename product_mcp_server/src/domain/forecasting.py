"""Calculs statistiques pour le forecasting (P2).

Fonctions pures, testables sans I/O. Aucun acces base.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from ..schemas.forecast import (
    CalculationBasis,
    DataQuality,
    StockHistoryPoint,
    TrendDirection,
)


def moving_average(values: list[float], window: int) -> list[float | None]:
    """Moyenne mobile centree. Renvoie None pour les points insuffisants."""
    out: list[float | None] = []
    for i in range(len(values)):
        if i + 1 < window:
            out.append(None)
            continue
        out.append(sum(values[i + 1 - window : i + 1]) / window)
    return out


def linear_regression_slope(y: list[float], x: list[float]) -> tuple[float, float, float]:
    """Renvoie (pente, intercept, r_squared) pour y = a*x + b."""
    n = len(y)
    if n < 2:
        return 0.0, 0.0, 0.0
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    num = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    den_x = sum((xi - mean_x) ** 2 for xi in x)
    den_y = sum((yi - mean_y) ** 2 for yi in y)
    if den_x == 0:
        return 0.0, mean_y, 0.0
    slope = num / den_x
    intercept = mean_y - slope * mean_x
    if den_y == 0:
        return slope, intercept, 0.0
    pred = [slope * xi + intercept for xi in x]
    ss_res = sum((yi - pi) ** 2 for yi, pi in zip(y, pred))
    r_squared = 1.0 - ss_res / den_y
    return slope, intercept, max(0.0, min(1.0, r_squared))


def trend_from_history(
    points: list[StockHistoryPoint],
) -> tuple[TrendDirection, float, float | None, float | None, DataQuality]:
    """Calcule tendance, pente moyenne par jour, R^2, MA7, qualite.

    Renvoie (direction, avg_daily_change, r_squared, moving_average_7d, quality).
    """
    if len(points) < 3:
        return TrendDirection.INSUFFICIENT_DATA, 0.0, None, None, DataQuality.LOW
    sorted_pts = sorted(points, key=lambda p: p.recorded_at)
    t0 = sorted_pts[0].recorded_at
    xs = [(p.recorded_at - t0).total_seconds() / 86400.0 for p in sorted_pts]
    ys = [float(p.quantity) for p in sorted_pts]
    slope, _, r2 = linear_regression_slope(ys, xs)
    ma7 = moving_average(ys, 7)
    last_ma = next((v for v in reversed(ma7) if v is not None), None)
    quality = _quality_from_points(len(sorted_pts), xs)
    if abs(slope) < 0.1:
        return TrendDirection.STABLE, 0.0, r2, last_ma, quality
    return (
        TrendDirection.RISING if slope > 0 else TrendDirection.FALLING,
        slope,
        r2,
        last_ma,
        quality,
    )


def _quality_from_points(count: int, xs: list[float]) -> DataQuality:
    if count < 7:
        return DataQuality.LOW
    span_days = max(xs[-1] - xs[0], 0.0)
    if count >= 30 and span_days >= 60:
        return DataQuality.HIGH
    if count >= 14 and span_days >= 14:
        return DataQuality.MEDIUM
    return DataQuality.LOW


_QUALITY_ORDER = {DataQuality.LOW: 0, DataQuality.MEDIUM: 1, DataQuality.HIGH: 2}


def estimate_stockout(
    current_quantity: int,
    avg_daily_movement: float,
    safety_buffer_days: int,
    last_date: datetime,
    min_quality: DataQuality = DataQuality.MEDIUM,
    quality: DataQuality = DataQuality.LOW,
) -> tuple[datetime | None, datetime | None, list[str], list[str]]:
    """Renvoie (stockout_date, reorder_date, hypotheses, limitations).

    Renvoie (None, None, ...) si qualite insuffisante ou mouvement nul.
    """
    hypotheses: list[str] = []
    limitations: list[str] = []
    if _QUALITY_ORDER[quality] < _QUALITY_ORDER[min_quality]:
        limitations.append(
            f"Data quality ({quality.value}) below threshold ({min_quality.value}); no date produced."
        )
        return None, None, hypotheses, limitations
    if avg_daily_movement <= 0:
        limitations.append(
            "Average daily movement is zero or negative; cannot estimate depletion."
        )
        return None, None, hypotheses, limitations
    if current_quantity <= 0:
        limitations.append("Current quantity is already zero.")
        return None, None, hypotheses, limitations

    from datetime import timedelta

    days_to_zero = current_quantity / avg_daily_movement
    stockout_date = last_date + timedelta(days=days_to_zero)
    reorder_date = stockout_date - timedelta(days=safety_buffer_days)
    hypotheses.append(
        f"Movement assumed stable at {avg_daily_movement:.2f} units/day over the historical window."
    )
    return stockout_date, reorder_date, hypotheses, limitations


def autocorrelation(values: list[float], lag: int) -> float:
    """Autocorrelation pour un lag donne. 0 si pas assez de points."""
    n = len(values)
    if lag <= 0 or lag >= n:
        return 0.0
    mean = sum(values) / n
    num = sum((values[i] - mean) * (values[i + lag] - mean) for i in range(n - lag))
    den = sum((v - mean) ** 2 for v in values)
    if den == 0:
        return 0.0
    return num / den


def best_periodicity(
    values: list[float],
    candidate_periods: Iterable[int],
    *,
    min_cycles: int = 2,
) -> tuple[int | None, float, int]:
    """Cherche la periodicite avec la plus forte autocorr (avec assez de cycles)."""
    best_lag: int | None = None
    best_score = 0.0
    cycles = 0
    for lag in candidate_periods:
        score = autocorrelation(values, lag)
        cyc = len(values) // lag if lag else 0
        if score > best_score and cyc >= min_cycles:
            best_score = score
            best_lag = lag
            cycles = cyc
    return best_lag, best_score, cycles


def monthly_peaks_and_lows(values_by_month: dict[int, list[float]]) -> tuple[list[int], list[int]]:
    """Mois (1..12) avec moyenne haute / basse, a partir d'une serie agregee par mois."""
    if not values_by_month:
        return [], []
    monthly_avg = {m: sum(v) / len(v) for m, v in values_by_month.items() if v}
    if not monthly_avg:
        return [], []
    sorted_months = sorted(monthly_avg.items(), key=lambda x: x[1])
    n = len(sorted_months)
    low = [m for m, _ in sorted_months[: max(1, n // 3)]]
    high = [m for m, _ in sorted_months[-max(1, n // 3) :]]
    return sorted(high), sorted(low)


def calculation_basis_default() -> CalculationBasis:
    return CalculationBasis.GENERIC_MOVEMENTS


__all__ = [
    "moving_average",
    "linear_regression_slope",
    "trend_from_history",
    "estimate_stockout",
    "autocorrelation",
    "best_periodicity",
    "monthly_peaks_and_lows",
    "calculation_basis_default",
]
