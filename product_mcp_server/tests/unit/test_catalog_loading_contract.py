"""Régression : le chargement du catalogue/fournisseurs doit lire la
vraie forme de réponse de l'API Produit externe (`{"results": [...]}`) et
pas une clé supposée (`"products"` / `"suppliers"`) qui n'a jamais existé
côté API réelle.

Bug trouvé en vérifiant les outils Analytics en conditions réelles
(2026-07-29) : `_load_full_catalog`/`_load_suppliers` cherchaient la
mauvaise clé, silencieusement vide pour le catalogue et carrément un
crash (`AttributeError`) pour les fournisseurs. Les mocks existants
utilisaient par erreur la même mauvaise clé que le code bugué, donc
aucun test ne le détectait malgré 85 tests passants.
"""

from __future__ import annotations

import httpx
import pytest

from src.clients.product_client import ProductClient
from src.domain.cache import CATALOG_CACHE, SUPPLIERS_CACHE
from src.tools.analytics_tools import _load_full_catalog, _load_suppliers


@pytest.fixture(autouse=True)
def _clear_shared_caches():
    # CATALOG_CACHE/SUPPLIERS_CACHE sont des singletons module-level
    # (TTL 300s/600s) partagés par tous les tests du process — sans ce
    # nettoyage, un test qui tourne avant/après pourrait lire ou poser un
    # résultat périmé au lieu de vraiment exercer le mock de ce test-ci.
    CATALOG_CACHE.clear()
    SUPPLIERS_CACHE.clear()
    yield
    CATALOG_CACHE.clear()
    SUPPLIERS_CACHE.clear()


REAL_SHAPE_PRODUCTS = {
    "count": 2,
    "limit": 100,
    "offset": 0,
    "results": [
        {"id": 1, "sku": "HB-LAP-1001", "name": "Laptop 14", "category": "Laptops", "unit_price": 799.0},
        {"id": 2, "sku": "HB-MON-2101", "name": "Monitor", "category": "Displays", "unit_price": 229.5},
    ],
}

REAL_SHAPE_SUPPLIERS = {
    "count": 1,
    "results": [
        {"id": "SUP-HBT-001", "name": "Holberton Tools Co.", "lead_time_days": 5},
    ],
}


def _client(payload: dict) -> ProductClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    return ProductClient(
        base_url="http://products.test",
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.asyncio
async def test_load_full_catalog_reads_results_key() -> None:
    client = _client(REAL_SHAPE_PRODUCTS)
    products, stale = await _load_full_catalog(client)
    assert len(products) == 2
    assert products[0]["sku"] == "HB-LAP-1001"
    assert stale is False


@pytest.mark.asyncio
async def test_load_suppliers_reads_results_key_and_does_not_crash() -> None:
    client = _client(REAL_SHAPE_SUPPLIERS)
    suppliers, _stale = await _load_suppliers(client)
    assert "SUP-HBT-001" in suppliers
    assert suppliers["SUP-HBT-001"]["name"] == "Holberton Tools Co."
