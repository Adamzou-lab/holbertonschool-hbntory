"""Tests unitaires du domaine profitabilite (E6). Decimal obligatoire."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from src.domain.profitability import (
    aggregate_supplier_cost,
    build_storage_efficiency,
    compute_product_margin,
    rank_products,
)
from src.schemas.margin import (
    ProfitabilityMetric,
    PurchaseEvent,
    SaleEvent,
    StorageRecommendation,
)

_NOW = datetime(2026, 6, 1, tzinfo=UTC)


def _sale(pid: int, bid: int, qty: int, amount: str, days_ago: int) -> SaleEvent:
    return SaleEvent(
        product_id=pid,
        branch_id=bid,
        quantity=qty,
        unit_sale_amount=Decimal(amount),
        currency="USD",
        occurred_at=_NOW - timedelta(days=days_ago),
    )


def _purchase(pid: int, sid: str, qty: int, cost: str, freight: str, days_ago: int) -> PurchaseEvent:
    return PurchaseEvent(
        product_id=pid,
        supplier_id=sid,
        quantity=qty,
        unit_purchase_cost=Decimal(cost),
        freight_cost=Decimal(freight),
        currency="USD",
        occurred_at=_NOW - timedelta(days=days_ago),
    )


def test_compute_margin_full_data() -> None:
    sales = [_sale(1, 1, 10, "100.00", 30), _sale(1, 1, 5, "100.00", 10)]
    purchases = [_purchase(1, "SUP-A", 20, "40.00", "10.00", 40)]
    m = compute_product_margin(1, sales, purchases, period_days=90, now=_NOW)
    assert m.units_sold == 15
    assert m.gross_revenue == Decimal("1500.00")
    # cogs = unit_cost * quantity (freight est separe)
    assert m.cost_of_goods_sold == Decimal("800.00")
    assert m.gross_margin == Decimal("700.00")
    assert m.has_purchase_data is True
    assert m.has_sales_data is True
    assert m.weighted_avg_unit_cost == Decimal("40.00")  # (40*20)/20


def test_compute_margin_no_purchase_data() -> None:
    sales = [_sale(1, 1, 10, "100.00", 30)]
    m = compute_product_margin(1, sales, [], period_days=90, now=_NOW)
    assert m.has_purchase_data is False
    assert m.has_sales_data is True
    assert m.gross_revenue == Decimal("1000.00")
    assert m.cost_of_goods_sold == Decimal("0")
    assert m.weighted_avg_unit_cost == Decimal("0")
    assert m.gross_margin_rate is None


def test_compute_margin_no_sales_data() -> None:
    purchases = [_purchase(1, "SUP-A", 20, "40.00", "10.00", 40)]
    m = compute_product_margin(1, [], purchases, period_days=90, now=_NOW)
    assert m.units_sold == 0
    assert m.gross_revenue == Decimal("0")
    assert m.has_purchase_data is True
    assert m.has_sales_data is False


def test_compute_margin_division_by_zero_safe() -> None:
    # qty minimum = 1 (contrainte Pydantic). On utilise des petites valeurs et un
    # cost de 0 pour verifier que les divisions sont protegees.
    sales = [_sale(1, 1, 1, "100.00", 30)]
    purchases = [_purchase(1, "SUP-A", 1, "0", "0", 30)]
    m = compute_product_margin(1, sales, purchases, period_days=90, now=_NOW)
    # Avec cost = 0 : margin = revenue, rate = 1, mais return_on_cost est None (den = 0).
    assert m.gross_margin == Decimal("100.00")
    assert m.return_on_cost is None


def test_rank_products_by_margin() -> None:
    sales = [
        _sale(1, 1, 10, "100.00", 30),
        _sale(2, 1, 5, "200.00", 30),
    ]
    purchases = [
        _purchase(1, "SUP-A", 10, "50.00", "0", 30),
        _purchase(2, "SUP-B", 5, "50.00", "0", 30),
    ]
    margins = [
        compute_product_margin(1, sales, purchases, period_days=90, now=_NOW),
        compute_product_margin(2, sales, purchases, period_days=90, now=_NOW),
    ]
    rows = rank_products(margins, metric=ProfitabilityMetric.GROSS_MARGIN, limit=5)
    assert rows[0].product_id == 2  # 5 * 200 - 5 * 50 = 750
    assert rows[1].product_id == 1  # 10 * 100 - 10 * 50 = 500


def test_rank_products_by_volume() -> None:
    sales = [_sale(1, 1, 10, "10.00", 30), _sale(2, 1, 20, "10.00", 30)]
    purchases = []
    margins = [
        compute_product_margin(1, sales, purchases, period_days=90, now=_NOW),
        compute_product_margin(2, sales, purchases, period_days=90, now=_NOW),
    ]
    rows = rank_products(margins, metric=ProfitabilityMetric.SALES_VOLUME, limit=5)
    assert rows[0].product_id == 2  # 20 > 10
    assert rows[1].product_id == 1


def test_aggregate_supplier_cost() -> None:
    purchases = [
        _purchase(1, "SUP-A", 10, "100.00", "5.00", 30),
        _purchase(2, "SUP-A", 5, "50.00", "2.00", 30),
        _purchase(3, "SUP-B", 10, "200.00", "0", 30),
    ]
    rows = aggregate_supplier_cost(purchases, period_days=90, now=_NOW)
    sup_a = next(r for r in rows if r.supplier_id == "SUP-A")
    # Total cost = (100*10+5) + (50*5+2) = 1005 + 252 = 1257
    assert sup_a.total_purchase_cost == Decimal("1250.00")
    assert sup_a.total_freight_cost == Decimal("7.00")
    assert sup_a.total_cost == Decimal("1257.00")
    assert sup_a.order_count == 2


def test_build_storage_efficiency_recommendation() -> None:
    from src.domain.storage_complexity import assess_complexity

    # Pas de ventes et pas de couts d'achat => units_sold=0 et gross_margin<=0 => DROP
    sales = []  # aucune vente
    purchases = [_purchase(1, "SUP-A", 5, "10.00", "0", 30)]
    margin = compute_product_margin(1, sales, purchases, period_days=90, now=_NOW)
    complexity_score, _ = assess_complexity({"weight_kg": 25.0, "category": "Furniture"})
    entries = build_storage_efficiency([margin], {1: complexity_score})
    assert entries[0].recommendation == StorageRecommendation.DROP_CANDIDATE


def test_build_storage_efficiency_keep() -> None:
    from src.domain.storage_complexity import assess_complexity

    sales = [_sale(1, 1, 100, "100.00", 30)]
    purchases = [_purchase(1, "SUP-A", 50, "10.00", "0", 30)]
    margin = compute_product_margin(1, sales, purchases, period_days=90, now=_NOW)
    complexity_score, _ = assess_complexity({"weight_kg": 1.0, "category": "Accessories"})
    entries = build_storage_efficiency([margin], {1: complexity_score})
    assert entries[0].recommendation == StorageRecommendation.KEEP
