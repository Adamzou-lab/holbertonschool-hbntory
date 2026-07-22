"""Fixtures pytest partagees par tous les tests."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from src.product_client import ProductClient

SAMPLE_PRODUCTS = [
    {"id": 1, "sku": "HB-LAP-1001", "name": "Holberton Student Laptop 14", "category": "Laptops", "unit_price": 799.0},
    {"id": 2, "sku": "HB-LAP-1002", "name": "Holberton Student Laptop 16", "category": "Laptops", "unit_price": 999.0},
    {"id": 3, "sku": "HB-MON-2101", "name": "27 inch Lab Monitor", "category": "Displays", "unit_price": 229.5},
]


def _make(handler: Callable[[httpx.Request], httpx.Response]) -> ProductClient:
    return ProductClient(
        base_url="http://products.test",
        timeout_seconds=2.0,
        transport=httpx.MockTransport(handler),
    )


@pytest.fixture
def make_product_client() -> Callable[..., ProductClient]:
    return _make


@pytest.fixture
def product_ok_factory() -> ProductClient:
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/api/v1/products":
            return httpx.Response(200, json={"products": SAMPLE_PRODUCTS, "total": len(SAMPLE_PRODUCTS), "limit": 20, "offset": 0})
        if req.url.path.startswith("/api/v1/products/search"):
            return httpx.Response(200, json={"products": SAMPLE_PRODUCTS[:1], "total": 1})
        if req.url.path.startswith("/api/v1/products/"):
            sku = req.url.path.rsplit("/", 1)[-1]
            match = next((p for p in SAMPLE_PRODUCTS if p["sku"] == sku or str(p["id"]) == sku), None)
            if match is None:
                return httpx.Response(404, json={"error": "not_found", "message": "Product not found."})
            return httpx.Response(200, json=match)
        return httpx.Response(404, json={"error": "not_found"})

    return _make(handler)


@pytest.fixture
def product_404_factory() -> ProductClient:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "not_found", "message": "Product not found."})

    return _make(handler)


@pytest.fixture
def product_500_factory() -> ProductClient:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "server_error"})

    return _make(handler)


@pytest.fixture
def product_disconnected_factory() -> ProductClient:
    """ProductClient dont le transport leve httpx.ConnectError."""

    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated network failure", request=req)

    return _make(handler)
