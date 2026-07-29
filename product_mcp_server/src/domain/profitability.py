"""Calculs financiers pour les outils de rentabilite (P3).

Tous les calculs utilisent Decimal (jamais float) pour eviter les erreurs
d'arrondi sur des valeurs monetaires.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from ..schemas.margin import (
    ProductMargin,
    ProfitabilityMetric,
    ProfitableProductEntry,
    PurchaseEvent,
    SaleEvent,
    StorageEfficiencyEntry,
    StorageRecommendation,
    SupplierCostEntry,
)

ZERO = Decimal("0")
CENT = Decimal("0.01")


def _q(d: Decimal) -> Decimal:
    """Quantize au centime (gestion monnaie)."""
    return d.quantize(CENT, rounding=ROUND_HALF_UP)


def _safe_div(num: Decimal, den: Decimal) -> Decimal | None:
    if den == ZERO:
        return None
    return num / den


def compute_product_margin(
    product_id: int,
    sales: list[SaleEvent],
    purchases: list[PurchaseEvent],
    *,
    period_days: int,
    now: datetime | None = None,
) -> ProductMargin:
    """Calcule la marge brute d'un produit sur la periode.

    Renvoie un objet ProductMargin ; ``has_sales_data``/``has_purchase_data``
    permettent de signaler les cas partiels.
    """
    now = now or datetime.utcnow()
    cutoff = now - timedelta(days=period_days)
    rel_sales = [s for s in sales if s.product_id == product_id and s.occurred_at >= cutoff]
    rel_purchases = [p for p in purchases if p.product_id == product_id and p.occurred_at >= cutoff]

    units_sold = sum(s.quantity for s in rel_sales)
    gross_revenue = sum((s.unit_sale_amount * s.quantity for s in rel_sales), start=ZERO)

    total_cost_qty: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for p in rel_purchases:
        total_cost_qty[p.currency] += p.unit_purchase_cost * p.quantity

    currency: str | None = None
    if rel_sales:
        currency = rel_sales[0].currency
    elif rel_purchases:
        currency = rel_purchases[0].currency
    if currency is None:
        currency = "USD"

    total_cost = total_cost_qty.get(currency, ZERO)
    margin = gross_revenue - total_cost
    # margin_rate et return_on_cost ne sont significatifs que si on a des couts d'achat.
    if rel_purchases and total_cost > ZERO:
        margin_rate = _safe_div(margin, gross_revenue)
        return_on_cost = _safe_div(margin, total_cost)
    else:
        margin_rate = None
        return_on_cost = None
    if rel_purchases:
        total_qty = sum(p.quantity for p in rel_purchases)
        weighted_unit_cost = (
            sum(p.unit_purchase_cost * p.quantity for p in rel_purchases) / total_qty
            if total_qty > 0
            else ZERO
        )
    else:
        weighted_unit_cost = ZERO

    return ProductMargin(
        product_id=product_id,
        period_days=period_days,
        units_sold=units_sold,
        gross_revenue=_q(gross_revenue),
        weighted_avg_unit_cost=_q(weighted_unit_cost),
        cost_of_goods_sold=_q(total_cost),
        gross_margin=_q(margin),
        gross_margin_rate=margin_rate,
        return_on_cost=return_on_cost,
        currency=currency,
        has_purchase_data=bool(rel_purchases),
        has_sales_data=bool(rel_sales),
    )


def rank_products(
    margins: list[ProductMargin],
    *,
    metric: ProfitabilityMetric,
    limit: int,
    names_by_id: dict[int, str] | None = None,
) -> list[ProfitableProductEntry]:
    """Classe les produits par metric et renvoie le top N."""
    names_by_id = names_by_id or {}
    enriched = []
    for m in margins:
        if metric == ProfitabilityMetric.GROSS_MARGIN:
            score = m.gross_margin
        elif metric == ProfitabilityMetric.GROSS_MARGIN_RATE:
            score = m.gross_margin_rate if m.gross_margin_rate is not None else Decimal("-1")
        elif metric == ProfitabilityMetric.SALES_VOLUME:
            score = Decimal(m.units_sold)
        elif metric == ProfitabilityMetric.RETURN_ON_COST:
            score = m.return_on_cost if m.return_on_cost is not None else Decimal("-1")
        else:
            score = m.gross_margin
        enriched.append((score, m))

    enriched.sort(key=lambda x: x[0], reverse=True)

    out: list[ProfitableProductEntry] = []
    for score, m in enriched[:limit]:
        out.append(
            ProfitableProductEntry(
                product_id=m.product_id,
                product_name=names_by_id.get(m.product_id),
                total_margin=m.gross_margin,
                units_sold=m.units_sold,
                gross_revenue=m.gross_revenue,
                return_on_cost=m.return_on_cost,
                currency=m.currency,
            )
        )
    return out


def aggregate_supplier_cost(
    purchases: list[PurchaseEvent],
    *,
    period_days: int,
    now: datetime | None = None,
    suppliers_by_id: dict[str, str] | None = None,
) -> list[SupplierCostEntry]:
    """Cout total d'achat par fournisseur sur la periode."""
    suppliers_by_id = suppliers_by_id or {}
    now = now or datetime.utcnow()
    cutoff = now - timedelta(days=period_days)

    by_supplier: dict[str, dict[str, Decimal | int | None]] = defaultdict(
        lambda: {
            "total_purchase_cost": ZERO,
            "total_freight_cost": ZERO,
            "total_cost": ZERO,
            "order_count": 0,
            "currency": "USD",
        }
    )

    for p in purchases:
        if p.occurred_at < cutoff:
            continue
        bucket = by_supplier[p.supplier_id]
        bucket["total_purchase_cost"] += p.unit_purchase_cost * p.quantity  # type: ignore[operator]
        bucket["total_freight_cost"] += p.freight_cost  # type: ignore[operator]
        bucket["total_cost"] = bucket["total_purchase_cost"] + bucket["total_freight_cost"]  # type: ignore[operator]
        bucket["order_count"] = int(bucket["order_count"]) + 1  # type: ignore[arg-type]
        bucket["currency"] = p.currency

    out = []
    for sid, b in by_supplier.items():
        out.append(
            SupplierCostEntry(
                supplier_id=sid,
                supplier_name=suppliers_by_id.get(sid),
                total_purchase_cost=_q(b["total_purchase_cost"]),  # type: ignore[arg-type]
                total_freight_cost=_q(b["total_freight_cost"]),  # type: ignore[arg-type]
                total_cost=_q(b["total_cost"]),  # type: ignore[arg-type]
                order_count=b["order_count"],  # type: ignore[arg-type]
                avg_lead_time_days=None,
                on_time_pct=None,
                currency=b["currency"],  # type: ignore[arg-type]
            )
        )
    return sorted(out, key=lambda e: e.total_cost, reverse=True)


def recommend_storage(
    margin: ProductMargin,
    complexity_score: int | None,
) -> StorageRecommendation:
    """Recommandation heuristique, NON automatique."""
    if complexity_score is None:
        complexity = 50
    else:
        complexity = complexity_score
    if margin.units_sold == 0 and margin.gross_margin <= ZERO:
        return StorageRecommendation.DROP_CANDIDATE
    if complexity >= 70 and margin.gross_margin < Decimal("100"):
        return StorageRecommendation.REDUCE
    if complexity >= 50 and margin.gross_margin < Decimal("50"):
        return StorageRecommendation.REVIEW
    return StorageRecommendation.KEEP


def build_storage_efficiency(
    margins: list[ProductMargin],
    complexity_by_id: dict[int, int],
    names_by_id: dict[int, str] | None = None,
) -> list[StorageEfficiencyEntry]:
    """Construit les entrees StorageEfficiency pour tous les produits analyses."""
    names_by_id = names_by_id or {}
    out: list[StorageEfficiencyEntry] = []
    for m in margins:
        complexity = complexity_by_id.get(m.product_id)
        rec = recommend_storage(m, complexity)
        if complexity is None or complexity == 0:
            margin_per_complexity = None
        else:
            margin_per_complexity = m.gross_margin / Decimal(complexity)
        rationale = _rationale_for(rec, m, complexity)
        out.append(
            StorageEfficiencyEntry(
                product_id=m.product_id,
                product_name=names_by_id.get(m.product_id),
                complexity_score=complexity,
                total_margin=m.gross_margin,
                units_sold=m.units_sold,
                margin_per_complexity=margin_per_complexity,
                recommendation=rec,
                rationale=rationale,
            )
        )
    return out


def _rationale_for(rec: StorageRecommendation, m: ProductMargin, complexity: int | None) -> str:
    if rec == StorageRecommendation.DROP_CANDIDATE:
        return "Aucune vente ni marge sur la periode ; candidat a la sortie (a valider humainement)."
    if rec == StorageRecommendation.REDUCE:
        return f"Complexite elevee ({complexity}) pour une marge faible ({m.gross_margin}). A reduire."
    if rec == StorageRecommendation.REVIEW:
        return f"Ratio marge/complexite a revoir manuellement (marge={m.gross_margin}, complexite={complexity})."
    return f"Marge positive et complexite acceptable (marge={m.gross_margin})."


__all__ = [
    "compute_product_margin",
    "rank_products",
    "aggregate_supplier_cost",
    "recommend_storage",
    "build_storage_efficiency",
]
