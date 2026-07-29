"""Tests de contrats pour les providers (E6).

Les providers HTTP et Fixture doivent respecter le meme contrat de
sortie. Toute deviation doit echouer immediatement.
"""

from __future__ import annotations

from datetime import datetime

from src.providers.forecast_fixture import FixtureForecastProvider
from src.schemas.forecast import StockHistoryPoint


async def test_fixture_forecast_provider_returns_valid_points() -> None:
    provider = FixtureForecastProvider()
    points = await provider.get_history(product_id=1, branch_id=1, days=30)
    assert isinstance(points, list)
    assert len(points) == 30
    for p in points:
        assert isinstance(p, StockHistoryPoint)
        assert p.quantity >= 0
        assert isinstance(p.recorded_at, datetime)
        # branch_id est attache via object.__setattr__ (en dehors du schema Pydantic)
        assert getattr(p, "_branch_id", None) is not None


async def test_fixture_forecast_provider_branches() -> None:
    """Sans branch_id, le provider genere pour plusieurs branches."""
    provider = FixtureForecastProvider()
    points = await provider.get_history(product_id=1, branch_id=None, days=10)
    branches = {getattr(p, "_branch_id", None) for p in points}
    assert len(branches) >= 2


async def test_fixture_forecast_provider_deterministic() -> None:
    """Meme seed -> meme serie."""
    p1 = FixtureForecastProvider()
    p2 = FixtureForecastProvider()
    pts1 = await p1.get_history(product_id=42, branch_id=1, days=20)
    pts2 = await p2.get_history(product_id=42, branch_id=1, days=20)
    assert [p.quantity for p in pts1] == [p.quantity for p in pts2]


async def test_fixture_forecast_provider_days_bounded() -> None:
    """days est borne a 3..365, valeurs hors borne ramenees au min."""
    provider = FixtureForecastProvider()
    pts_short = await provider.get_history(product_id=1, branch_id=1, days=1)
    pts_long = await provider.get_history(product_id=1, branch_id=1, days=1000)
    assert len(pts_short) >= 3  # min
    assert len(pts_long) <= 365  # max


async def test_profitability_fixture_returns_synthetic_data() -> None:
    from src.providers.profitability_fixture import FixtureProfitabilityProvider

    provider = FixtureProfitabilityProvider()
    data = await provider.get_events(days=30, seed=42)
    # Tous les evenements portent data_origin=synthetic_demo
    assert all(s.data_origin == "synthetic_demo" for s in data.sales)
    assert all(p.data_origin == "synthetic_demo" for p in data.purchases)
    assert len(data.sales) > 0
    assert len(data.purchases) > 0
    for s in data.sales:
        assert s.currency == "USD"
    for p in data.purchases:
        assert p.currency == "USD"
        assert p.unit_purchase_cost >= 0


async def test_profitability_fixture_deterministic() -> None:
    from src.providers.profitability_fixture import FixtureProfitabilityProvider

    p1 = FixtureProfitabilityProvider()
    p2 = FixtureProfitabilityProvider()
    d1 = await p1.get_events(days=30, seed=99)
    d2 = await p2.get_events(days=30, seed=99)
    assert len(d1.sales) == len(d2.sales)
    assert len(d1.purchases) == len(d2.purchases)
    # Premieres coordonnees identiques
    assert d1.sales[0].quantity == d2.sales[0].quantity
