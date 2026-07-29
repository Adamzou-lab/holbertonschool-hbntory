"""Tests unitaires du domaine forecasting (E6)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.domain.forecasting import (
    autocorrelation,
    best_periodicity,
    estimate_stockout,
    linear_regression_slope,
    moving_average,
    trend_from_history,
)
from src.schemas.forecast import (
    DataQuality,
    StockHistoryPoint,
    TrendDirection,
)


def _point(days_ago: int, qty: int) -> StockHistoryPoint:
    return StockHistoryPoint(
        recorded_at=datetime.now(UTC) - timedelta(days=days_ago),
        quantity=qty,
        movement=None,
    )


def test_moving_average_short_window() -> None:
    out = moving_average([1.0, 2.0, 3.0, 4.0], window=3)
    assert out == [None, None, 2.0, 3.0]


def test_linear_regression_simple_line() -> None:
    slope, intercept, r2 = linear_regression_slope([1.0, 2.0, 3.0, 4.0], [0.0, 1.0, 2.0, 3.0])
    assert abs(slope - 1.0) < 1e-9
    assert abs(intercept - 1.0) < 1e-9
    assert r2 == 1.0


def test_linear_regression_constant() -> None:
    slope, intercept, r2 = linear_regression_slope([5.0, 5.0, 5.0], [0.0, 1.0, 2.0])
    assert slope == 0.0
    assert intercept == 5.0
    assert r2 == 0.0


def test_trend_insufficient_data() -> None:
    direction, slope, r2, ma, quality = trend_from_history([_point(0, 10)])
    assert direction == TrendDirection.INSUFFICIENT_DATA
    assert quality == DataQuality.LOW


def test_trend_rising() -> None:
    """Plus recent = plus de stock -> RISING."""
    points = [_point(i, 10 + i * 5) for i in range(20)]
    direction, slope, r2, ma, quality = trend_from_history(points)
    # Quand on regarde du plus ancien au plus recent :
    # earliest (i=19) = qty 105, latest (i=0) = qty 10 : c'est FALLING.
    # Pour tester RISING : plus recent = plus haut. Donc qty decroit avec days_ago.
    points = [_point(i, 100 - i * 5) for i in range(20)]  # plus recent = plus haut
    direction, slope, r2, ma, quality = trend_from_history(points)
    assert direction == TrendDirection.RISING
    assert slope > 0


def test_trend_falling() -> None:
    """Plus recent = moins de stock -> FALLING."""
    points = [_point(i, 10 + i * 5) for i in range(20)]  # plus recent = moins
    direction, slope, r2, ma, quality = trend_from_history(points)
    assert direction == TrendDirection.FALLING
    assert slope < 0


def test_trend_stable_small_slope() -> None:
    points = [_point(i, 50 + (i % 3)) for i in range(20)]
    direction, slope, r2, ma, quality = trend_from_history(points)
    # Slope tres faible : STABLE
    assert direction == TrendDirection.STABLE


def test_estimate_stockout_low_quality_no_dates() -> None:
    last = datetime.now(UTC)
    stockout, reorder, hyp, lim = estimate_stockout(
        current_quantity=10,
        avg_daily_movement=1.0,
        safety_buffer_days=7,
        last_date=last,
        quality=DataQuality.LOW,
    )
    assert stockout is None
    assert reorder is None


def test_estimate_stockout_zero_movement_no_dates() -> None:
    last = datetime.now(UTC)
    stockout, reorder, hyp, lim = estimate_stockout(
        current_quantity=10,
        avg_daily_movement=0.0,
        safety_buffer_days=7,
        last_date=last,
        quality=DataQuality.HIGH,
    )
    assert stockout is None


def test_estimate_stockout_produces_dates_when_quality_high() -> None:
    last = datetime.now(UTC)
    stockout, reorder, hyp, lim = estimate_stockout(
        current_quantity=20,
        avg_daily_movement=2.0,
        safety_buffer_days=7,
        last_date=last,
        quality=DataQuality.HIGH,
    )
    assert stockout is not None
    assert reorder is not None
    # reorder_date = stockout_date - 7 jours
    assert abs((stockout - reorder).days - 7) <= 1  # tolerance 1 jour (timing)


def test_autocorrelation_with_lag() -> None:
    # Serie qui se repete tous les 4 : autocorrelation a lag=4 devrait etre elevee.
    series = [1, 2, 3, 4, 1, 2, 3, 4, 1, 2, 3, 4]
    # Pour une serie parfaitement periodique 1-2-3-4, autocorr a lag=4 = (n-lag)/n * cycle_corr
    # Avec n=12, lag=4 : autocorr = (12-4)/12 = 0.667
    assert autocorrelation(series, 4) > 0.5


def test_autocorrelation_perfect_repetition() -> None:
    """Une serie exactement repetee 2 fois -> autocorr elevee a la periode."""
    series = [1, 2, 3, 1, 2, 3]
    # Pour [1,2,3,1,2,3] avec lag=3 : autocorr = (n-lag)/n = 3/6 = 0.5 (avec normalisation)
    assert autocorrelation(series, 3) > 0.4


def test_autocorrelation_zero_for_independent() -> None:
    import random

    rng = random.Random(42)
    series = [rng.random() for _ in range(50)]
    assert abs(autocorrelation(series, 1)) < 0.4


def test_best_periodicity_picks_7_day_cycle() -> None:
    # Serie de 28 jours avec cycle de 7 jours
    series = [(i % 7) for i in range(28)]
    best_lag, score, cycles = best_periodicity(series, candidate_periods=[7, 30, 90])
    assert best_lag == 7
    assert cycles >= 2


def test_best_periodicity_insufficient_data() -> None:
    series = [1, 2, 3]
    best_lag, score, cycles = best_periodicity(series, candidate_periods=[7, 30, 90])
    assert best_lag is None
