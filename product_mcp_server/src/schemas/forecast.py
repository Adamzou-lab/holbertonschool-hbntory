"""Schemas des outils de forecasting (P2)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class DataQuality(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TrendDirection(str, Enum):
    RISING = "rising"
    FALLING = "falling"
    STABLE = "stable"
    INSUFFICIENT_DATA = "insufficient_data"


class CalculationBasis(str, Enum):
    CLASSIFIED_MOVEMENTS = "classified_movements"
    GENERIC_MOVEMENTS = "generic_movements"
    SNAPSHOT_DELTAS = "snapshot_deltas"
    FIXTURE_SERIES = "fixture_series"


class StockHistorySeries(BaseModel):
    """Serie d'historique pour un produit sur une branche donnee."""

    model_config = ConfigDict(extra="forbid")

    branch_id: int
    branch_name: str | None = None
    points: list[StockHistoryPoint] = Field(default_factory=list)
    missing_days: int = Field(default=0, ge=0)


class StockHistoryPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recorded_at: datetime
    quantity: int = Field(ge=0)
    movement: int | None = Field(default=None, description="Delta par rapport au point precedent.")


class TrendSeries(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch_id: int
    branch_name: str | None = None
    direction: TrendDirection
    avg_daily_change: float
    r_squared: float | None = Field(default=None, ge=0, le=1)
    moving_average_7d: float | None = None
    data_quality: DataQuality


class StockoutForecast(BaseModel):
    """Sortie du tool forecast_stockout_and_reorder.

    Champs ``None`` quand le calcul est impossible (qualite trop faible).
    """

    model_config = ConfigDict(extra="forbid")

    product_id: int
    branch_id: int
    current_quantity: int = Field(ge=0)
    avg_daily_movement: float | None = None
    safety_buffer_days: int = Field(ge=0)
    estimated_stockout_date: datetime | None = None
    recommended_reorder_date: datetime | None = None
    hypotheses: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    data_quality: DataQuality = DataQuality.LOW


class SeasonalPattern(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: int
    has_pattern: bool
    candidate_periods_days: list[int] = Field(default_factory=list)
    peak_months: list[int] = Field(default_factory=list)
    low_months: list[int] = Field(default_factory=list)
    autocorrelation_at_best_lag: float | None = Field(default=None, ge=-1, le=1)
    cycles_completed: int = Field(default=0, ge=0)
    data_quality: DataQuality = DataQuality.LOW


StockHistorySeries.model_rebuild()

__all__ = [
    "DataQuality",
    "TrendDirection",
    "CalculationBasis",
    "StockHistorySeries",
    "StockHistoryPoint",
    "TrendSeries",
    "StockoutForecast",
    "SeasonalPattern",
]
