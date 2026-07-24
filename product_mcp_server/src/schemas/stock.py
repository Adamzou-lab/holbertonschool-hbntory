"""Schemas lies au stock HBntory."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BranchInfo(BaseModel):
    """Vue resumee d'une branche HBntory."""

    model_config = ConfigDict(extra="forbid")

    id: int = Field(description="Identifiant numerique de la branche.")
    name: str = Field(description="Nom affiche de la branche.")


class StockByBranch(BaseModel):
    """Une ligne de stock par branche pour un produit donne."""

    model_config = ConfigDict(extra="forbid")

    branch_id: int = Field(description="ID de la branche.")
    branch_name: str | None = Field(default=None, description="Nom lisible de la branche.")
    quantity: int = Field(ge=0, description="Quantite disponible (toujours >= 0).")


class StockByProduct(BaseModel):
    """Une ligne de stock par produit pour une branche donnee."""

    model_config = ConfigDict(extra="forbid")

    product_id: int = Field(description="ID numerique interne du produit.")
    quantity: int = Field(ge=0)


class StockHistoryPoint(BaseModel):
    """Un point d'historique de stock (serie temporelle)."""

    model_config = ConfigDict(extra="forbid")

    branch_id: int
    branch_name: str | None = None
    quantity: int = Field(ge=0)
    recorded_at: datetime


class ShoppingListItem(BaseModel):
    """Un item d'une shopping-list envoyee au tool de matching."""

    model_config = ConfigDict(extra="forbid")

    product_id: int = Field(description="ID numerique interne (toujours resolu en amont).")
    quantity: int = Field(ge=1, description="Quantite demandee (entier strictement positif).")


class ShoppingListFulfillment(BaseModel):
    """Resultat de fulfillment d'une shopping-list pour une branche."""

    model_config = ConfigDict(extra="forbid")

    branch_id: int
    branch_name: str | None = None
    items: list[dict] = Field(default_factory=list)
    missing: list[dict] = Field(default_factory=list)


__all__ = [
    "BranchInfo",
    "StockByBranch",
    "StockByProduct",
    "StockHistoryPoint",
    "ShoppingListItem",
    "ShoppingListFulfillment",
]
