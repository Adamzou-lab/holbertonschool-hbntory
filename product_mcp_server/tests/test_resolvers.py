"""Tests unitaires de src.resolvers (option C)."""

from __future__ import annotations

import httpx
import pytest

from src.errors import ResolverError
from src.product_client import ProductClient
from src.resolvers import clear_sku_cache, resolve_product_id, resolve_product_id_cached


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    """Vide le cache LRU entre chaque test."""
    clear_sku_cache()


def _client_with_sku(sku_to_id: dict[str, int]) -> ProductClient:
    """Client dont get(sku) renvoie un produit avec id."""

    def handler(req: httpx.Request) -> httpx.Response:
        sku = req.url.path.rsplit("/", 1)[-1]
        pid = sku_to_id.get(sku)
        if pid is None:
            return httpx.Response(404, json={"error": "not_found"})
        return httpx.Response(200, json={"id": pid, "sku": sku, "name": f"Product {sku}"})

    return ProductClient(
        base_url="http://products.test",
        timeout_seconds=2.0,
        transport=httpx.MockTransport(handler),
    )


async def test_numeric_string_returns_int_directly() -> None:
    client = _client_with_sku({})
    assert await resolve_product_id("1", client) == 1
    assert await resolve_product_id("42", client) == 42


async def test_zero_is_rejected() -> None:
    client = _client_with_sku({})
    with pytest.raises(ResolverError):
        await resolve_product_id("0", client)


async def test_negative_string_rejected() -> None:
    client = _client_with_sku({})
    with pytest.raises(ResolverError):
        await resolve_product_id("-5", client)


async def test_empty_string_rejected() -> None:
    client = _client_with_sku({})
    with pytest.raises(ResolverError):
        await resolve_product_id("", client)


async def test_none_rejected() -> None:
    client = _client_with_sku({})
    with pytest.raises(ResolverError):
        await resolve_product_id(None, client)  # type: ignore[arg-type]


async def test_sku_resolves_via_api() -> None:
    client = _client_with_sku({"HB-LAP-1001": 1})
    assert await resolve_product_id("HB-LAP-1001", client) == 1


async def test_sku_lowercase_prefix_is_normalized() -> None:
    """Le resolver est insensible a la casse sur le prefixe : 'hb-...'
    est accepte et resolu comme 'HB-...'."""
    client = _client_with_sku({"HB-LAP-1001": 1})
    assert await resolve_product_id("hb-lap-1001", client) == 1


async def test_unknown_format_rejected() -> None:
    client = _client_with_sku({})
    with pytest.raises(ResolverError):
        await resolve_product_id("foo-bar", client)


async def test_sku_not_found_propagates_as_resolver_error() -> None:
    client = _client_with_sku({})
    with pytest.raises(ResolverError):
        await resolve_product_id("HB-FAUX-9999", client)


async def test_sku_with_non_int_id_propagates_as_resolver_error() -> None:
    """Si l'API renvoie un produit sans champ id entier valide."""

    def handler(req: httpx.Request) -> httpx.Response:
        sku = req.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, json={"sku": sku, "name": "broken"})

    client = ProductClient(
        base_url="http://products.test",
        timeout_seconds=2.0,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ResolverError):
        await resolve_product_id("HB-BAD-0001", client)


async def test_cache_returns_same_int_without_recalling_api() -> None:
    """Le cache doit servir les appels successifs sans nouvel appel HTTP."""
    calls: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        sku = req.url.path.rsplit("/", 1)[-1]
        calls.append(sku)
        return httpx.Response(200, json={"id": 7, "sku": sku})

    client = ProductClient(
        base_url="http://products.test",
        timeout_seconds=2.0,
        transport=httpx.MockTransport(handler),
    )

    a = await resolve_product_id_cached("HB-LAP-1001", client)
    b = await resolve_product_id_cached("HB-LAP-1001", client)
    assert a == b == 7
    assert calls == ["HB-LAP-1001"], f"cache ineffective, calls={calls}"


async def test_cache_does_not_apply_to_numeric_path() -> None:
    """Le numerique n'a pas besoin de cache (pas d'appel HTTP)."""
    calls: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req.url.path)
        return httpx.Response(200, json={"id": 1})

    client = ProductClient(
        base_url="http://products.test",
        timeout_seconds=2.0,
        transport=httpx.MockTransport(handler),
    )

    await resolve_product_id_cached("5", client)
    await resolve_product_id_cached("5", client)
    assert calls == [], "numeric path must not hit the API"
