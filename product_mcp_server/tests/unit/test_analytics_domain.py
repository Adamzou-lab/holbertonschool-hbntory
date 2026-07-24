"""Tests unitaires du domaine analytics (E6)."""

from __future__ import annotations

from src.domain.catalog_analytics import (
    aggregate_by_category,
    aggregate_suppliers,
    estimate_inventory_value,
    extreme_prices,
    extreme_weights,
)
from src.domain.storage_complexity import METHODOLOGY, assess_complexity


def test_aggregate_by_category_handles_missing_values() -> None:
    products = [
        {"id": 1, "sku": "HB-A", "name": "A", "category": "Laptops", "unit_price": 100.0, "weight_kg": 1.0},
        {"id": 2, "sku": "HB-B", "name": "B", "category": "Laptops", "weight_kg": 2.0},  # pas de prix
        {"id": 3, "sku": "HB-C", "name": "C", "category": "Accessories", "unit_price": 10.0},  # pas de poids
        {"id": 4, "sku": "HB-D", "name": "D", "category": "Accessories", "unit_price": 20.0, "weight_kg": 0.5},
    ]
    cats = aggregate_by_category(products)
    by_cat = {c["category"]: c for c in cats}
    assert by_cat["Laptops"]["product_count"] == 2
    assert by_cat["Laptops"]["missing_price_count"] == 1
    assert by_cat["Laptops"]["avg_price"] == 100.0
    assert by_cat["Accessories"]["product_count"] == 2
    assert by_cat["Accessories"]["missing_weight_count"] == 1


def test_aggregate_by_category_handles_unknown_category() -> None:
    products = [{"id": 1, "sku": "HB-X", "name": "X"}]  # pas de categorie
    cats = aggregate_by_category(products)
    assert cats[0]["category"] == "Unknown"


def test_extreme_prices_filters_none_and_limits() -> None:
    products = [
        {"sku": "HB-A", "name": "A", "unit_price": 10.0},
        {"sku": "HB-B", "name": "B", "unit_price": 200.0},
        {"sku": "HB-C", "name": "C"},  # pas de prix
        {"sku": "HB-D", "name": "D", "unit_price": 50.0},
    ]
    top = extreme_prices(products, "highest", 2)
    assert len(top) == 2
    assert top[0]["sku"] == "HB-B"
    assert top[1]["sku"] == "HB-D"

    bottom = extreme_prices(products, "lowest", 2)
    assert bottom[0]["sku"] == "HB-A"
    assert bottom[1]["sku"] == "HB-D"


def test_extreme_prices_filters_by_category() -> None:
    products = [
        {"sku": "HB-A", "name": "A", "category": "Laptops", "unit_price": 1000.0},
        {"sku": "HB-B", "name": "B", "category": "Accessories", "unit_price": 5.0},
    ]
    top = extreme_prices(products, "highest", 5, category="Laptops")
    assert len(top) == 1
    assert top[0]["sku"] == "HB-A"


def test_extreme_weights_reports_missing() -> None:
    products = [
        {"sku": "HB-A", "name": "A", "weight_kg": 10.0},
        {"sku": "HB-B", "name": "B", "weight_kg": 2.0},
        {"sku": "HB-C", "name": "C"},  # pas de poids
    ]
    rows, missing = extreme_weights(products, "heaviest", 5)
    assert len(rows) == 2
    assert rows[0]["sku"] == "HB-A"
    assert missing == 1


def test_aggregate_suppliers_no_suppliers_metadata() -> None:
    products = [
        {"id": 1, "sku": "HB-A", "name": "A", "supplier_id": "SUP-1", "category": "X", "unit_price": 10.0},
        {"id": 2, "sku": "HB-B", "name": "B", "supplier_id": "SUP-1", "category": "Y", "unit_price": 20.0},
        {"id": 3, "sku": "HB-C", "name": "C", "supplier_id": "SUP-2", "category": "X"},
    ]
    suppliers = {"SUP-1": {"name": "Acme", "country": "US", "lead_time_days": 5, "reliability_score": 0.9}}
    rows = aggregate_suppliers(products, suppliers)
    assert len(rows) == 2
    sup1 = next(r for r in rows if r["supplier_id"] == "SUP-1")
    assert sup1["product_count"] == 2
    assert sup1["supplier_name"] == "Acme"
    assert set(sup1["categories_covered"]) == {"X", "Y"}


def test_estimate_inventory_value_warns_no_purchase_cost() -> None:
    products = [
        {"id": 1, "sku": "HB-A", "name": "A", "category": "X", "unit_price": 10.0},
    ]
    stock_by_product = {1: 5}
    branches = [{"id": 1, "name": "Paris"}]
    result = estimate_inventory_value(products, stock_by_product, branches)
    assert result["total_value"] == 50.0
    assert "prix catalogue" in result["warning"]


def test_estimate_inventory_value_handles_missing_price() -> None:
    products = [{"id": 1, "sku": "HB-A", "name": "A"}]  # pas de prix
    result = estimate_inventory_value(products, {1: 5}, [{"id": 1, "name": "Paris"}])
    assert result["total_value"] == 0.0
    assert result["missing_price_count"] == 1


def test_assess_complexity_methodology_v1() -> None:
    assert METHODOLOGY == "heuristic_v1"
    score, factors = assess_complexity(
        {"weight_kg": 20.0, "category": "Furniture", "discontinued": True, "tags": ["legacy"]}
    )
    # weight=100, cat=80, disc=100, tags=80 → 0.4*100 + 0.3*80 + 0.2*100 + 0.1*80 = 40+24+20+8 = 92
    assert score == 92
    assert factors["weight_score"] == 100.0
    assert factors["category_risk_score"] == 80.0


def test_assess_complexity_low_risk_product() -> None:
    score, factors = assess_complexity(
        {"weight_kg": 0.5, "category": "Accessories", "discontinued": False, "tags": []}
    )
    # weight=2.5, cat=20, disc=0, tags=10 → 0.4*2.5+0.3*20+0.2*0+0.1*10 = 1+6+0+1 = 8
    assert score == 8


def test_assess_complexity_no_weight() -> None:
    score, factors = assess_complexity({"category": "Laptops"})
    assert score >= 0
    assert factors["weight_score"] == 0.0
