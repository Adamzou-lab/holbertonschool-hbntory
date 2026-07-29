"""Schemas des outils de rentabilite (P3 — donnees synthetiques)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ProfitabilityMetric(str, Enum):
    GROSS_MARGIN = "gross_margin"
    GROSS_MARGIN_RATE = "gross_margin_rate"
    SALES_VOLUME = "sales_volume"
    RETURN_ON_COST = "return_on_cost"


class StorageRecommendation(str, Enum):
    KEEP = "keep"
    REVIEW = "review"
    REDUCE = "reduce"
    DROP_CANDIDATE = "drop_candidate"


class SaleEvent(BaseModel):
    """Evenement de vente synthetique (jamais issu d'une source reelle)."""

    model_config = ConfigDict(extra="forbid")

    product_id: int
    branch_id: int
    quantity: int = Field(ge=1)
    unit_sale_amount: Decimal = Field(ge=Decimal("0"))
    currency: str
    occurred_at: datetime
    data_origin: str = "synthetic_demo"


class PurchaseEvent(BaseModel):
    """Evenement d'achat fournisseur synthetique."""

    model_config = ConfigDict(extra="forbid")

    product_id: int
    supplier_id: str
    quantity: int = Field(ge=1)
    unit_purchase_cost: Decimal = Field(ge=Decimal("0"))
    freight_cost: Decimal = Field(ge=Decimal("0"))
    currency: str
    occurred_at: datetime
    data_origin: str = "synthetic_demo"


class ProfitabilityData(BaseModel):
    """Dataset synthetique : ventes + achats sur une periode."""

    model_config = ConfigDict(extra="forbid")

    sales: list[SaleEvent] = Field(default_factory=list)
    purchases: list[PurchaseEvent] = Field(default_factory=list)
    generated_at: datetime
    seed: int


class ProductMargin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: int
    product_name: str | None = None
    period_days: int = Field(ge=1)
    units_sold: int = Field(ge=0)
    gross_revenue: Decimal
    weighted_avg_unit_cost: Decimal
    cost_of_goods_sold: Decimal
    gross_margin: Decimal
    gross_margin_rate: Decimal | None = Field(default=None, description="Entre 0 et 1 (0.25 = 25%).")
    return_on_cost: Decimal | None = None
    currency: str
    has_purchase_data: bool = Field(default=False)
    has_sales_data: bool = Field(default=False)


class ProfitableProductEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: int
    product_name: str | None = None
    total_margin: Decimal
    units_sold: int = Field(ge=0)
    gross_revenue: Decimal
    return_on_cost: Decimal | None = None
    currency: str


class SupplierCostEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier_id: str
    supplier_name: str | None = None
    total_purchase_cost: Decimal
    total_freight_cost: Decimal
    total_cost: Decimal
    order_count: int = Field(ge=0)
    avg_lead_time_days: float | None = None
    on_time_pct: float | None = Field(default=None, ge=0, le=1)
    currency: str


class StorageEfficiencyEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: int
    product_name: str | None = None
    complexity_score: int | None = Field(default=None, ge=0, le=100)
    total_margin: Decimal
    units_sold: int = Field(ge=0)
    margin_per_complexity: Decimal | None = None
    recommendation: StorageRecommendation
    rationale: str


__all__ = [
    "ProfitabilityMetric",
    "StorageRecommendation",
    "SaleEvent",
    "PurchaseEvent",
    "ProfitabilityData",
    "ProductMargin",
    "ProfitableProductEntry",
    "SupplierCostEntry",
    "StorageEfficiencyEntry",
]
