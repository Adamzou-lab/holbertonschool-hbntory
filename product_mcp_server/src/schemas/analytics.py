"""Schemas des outils d'analyse (P1)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CategoryStat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    product_count: int = Field(ge=0)
    avg_price: float | None = None
    min_price: float | None = None
    max_price: float | None = None
    total_weight_kg: float | None = None
    missing_price_count: int = Field(default=0, ge=0)
    missing_weight_count: int = Field(default=0, ge=0)
    currencies: list[str] = Field(default_factory=list)


class ExtremePriceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku: str
    name: str
    category: str | None = None
    unit_price: float
    currency: str | None = None
    weight_kg: float | None = None


class ExtremeWeightEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku: str
    name: str
    category: str | None = None
    weight_kg: float
    unit_price: float | None = None


class SupplierStat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier_id: str
    supplier_name: str | None = None
    country: str | None = None
    lead_time_days: int | None = None
    reliability_score: float | None = None
    product_count: int = Field(ge=0)
    categories_covered: list[str] = Field(default_factory=list)
    avg_price: float | None = None


class InventoryValueByCategory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    value: float
    currency: str | None = None
    item_count: int = Field(ge=0)


class InventoryValueByBranch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch_id: int
    branch_name: str | None = None
    value: float
    currency: str | None = None
    item_count: int = Field(ge=0)


class ComplexityFactor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weight_score: float = Field(ge=0, le=100)
    category_risk_score: float = Field(ge=0, le=100)
    discontinued_score: float = Field(ge=0, le=100)
    tags_score: float = Field(ge=0, le=100)
    methodology: str = "heuristic_v1"


class ComplexityEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku: str
    name: str
    weight_kg: float | None = None
    category: str | None = None
    complexity_score: int = Field(ge=0, le=100)
    factors: ComplexityFactor


class DiscontinuedEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku: str
    name: str
    category: str | None = None
    total_stock: int = Field(ge=0)
    branches: list[dict] = Field(default_factory=list)
    review_required: bool = True


class BranchStockShare(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch_id: int
    branch_name: str | None = None
    total_items: int = Field(ge=0)
    total_units: int = Field(ge=0)
    top_categories: list[dict] = Field(default_factory=list)


class StockConcentration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gini_index: float = Field(ge=0, le=1, description="0 = repartition egale, 1 = monopolistique.")
    top_branch_share: float = Field(ge=0, le=1)
    method: str = "absolute_units"


class OverstockedEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: int
    total_units: int = Field(ge=0)
    branches: list[dict] = Field(default_factory=list)


class UnderstockedEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: int
    total_units: int = Field(ge=0)
    branches: list[dict] = Field(default_factory=list)


__all__ = [
    "CategoryStat",
    "ExtremePriceEntry",
    "ExtremeWeightEntry",
    "SupplierStat",
    "InventoryValueByCategory",
    "InventoryValueByBranch",
    "ComplexityEntry",
    "ComplexityFactor",
    "DiscontinuedEntry",
    "BranchStockShare",
    "StockConcentration",
    "OverstockedEntry",
    "UnderstockedEntry",
]
