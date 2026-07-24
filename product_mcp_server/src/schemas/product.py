"""Schemas lies aux produits du catalogue."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ProductSummary(BaseModel):
    """Vue resumee d'un produit (utilisee par les classements analytics)."""

    model_config = ConfigDict(extra="forbid")

    sku: str = Field(description="SKU du produit (cle publique).")
    name: str = Field(description="Nom affiche du produit.")
    category: str | None = Field(default=None, description="Categorie (peut etre inconnue).")
    unit_price: float | None = Field(
        default=None,
        description="Prix unitaire catalogue. None si non renseigne par l'API Produit.",
    )
    currency: str | None = Field(default=None, description="Devise du prix catalogue.")
    weight_kg: float | None = Field(default=None, description="Poids en kg (peut etre null).")
    discontinued: bool = Field(default=False, description="Produit marque discontinue.")


class ProductDetail(ProductSummary):
    """Detail complet d'un produit, tel que renvoye par l'API externe."""

    model_config = ConfigDict(extra="ignore")

    product_id: int | None = Field(default=None, description="Identifiant numerique interne.")
    brand: str | None = Field(default=None)
    supplier_id: str | None = Field(default=None)
    supplier_name: str | None = Field(default=None)
    description: str | None = Field(default=None)
    tags: list[str] = Field(default_factory=list)
    updated_at: str | None = Field(default=None)


__all__ = ["ProductSummary", "ProductDetail"]
