"""Tests pagination + cache (E6)."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from src.domain.cache import TTLCache
from src.domain.pagination import paginate_all
from src.errors import InvalidInputError


async def test_paginate_all_single_page() -> None:
    async def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/api/v1/products":
            return httpx.Response(200, json={"products": [{"id": 1, "sku": "A"}]})
        return httpx.Response(404)

    def fetch(offset: int, limit: int):
        async def _do() -> dict:
            transport = httpx.MockTransport(handler)
            async with httpx.AsyncClient(transport=transport) as client:
                r = await client.get(
                    "http://test/api/v1/products",
                    params={"offset": offset, "limit": limit},
                )
                return r.json()

        return _do()

    items = await paginate_all(fetch, page_size=10, results_key="products")
    assert len(items) == 1
    assert items[0]["sku"] == "A"


async def test_paginate_all_multiple_pages() -> None:
    page_calls = {"count": 0}

    async def handler(req: httpx.Request) -> httpx.Response:
        page_calls["count"] += 1
        offset = int(req.url.params.get("offset", 0))
        limit = int(req.url.params.get("limit", 100))
        # 3 pages de 100, 100, 50 = 250 items
        if offset == 0:
            return httpx.Response(200, json={"products": [{"id": i} for i in range(100)]})
        if offset == 100:
            return httpx.Response(200, json={"products": [{"id": i} for i in range(100, 200)]})
        if offset == 200:
            return httpx.Response(200, json={"products": [{"id": i} for i in range(200, 250)]})
        return httpx.Response(200, json={"products": []})

    def fetch(offset: int, limit: int):
        async def _do() -> dict:
            transport = httpx.MockTransport(handler)
            async with httpx.AsyncClient(transport=transport) as client:
                r = await client.get(
                    "http://test/api/v1/products",
                    params={"offset": offset, "limit": limit},
                )
                return r.json()

        return _do()

    items = await paginate_all(fetch, page_size=100, results_key="products")
    assert len(items) == 250


async def test_paginate_all_max_pages_safety() -> None:
    async def handler(req: httpx.Request) -> httpx.Response:
        offset = int(req.url.params.get("offset", 0))
        # Renvoie toujours une page pleine pour forcer la boucle
        return httpx.Response(
            200,
            json={"products": [{"id": offset + i} for i in range(100)]},
        )

    def fetch(offset: int, limit: int):
        async def _do() -> dict:
            transport = httpx.MockTransport(handler)
            async with httpx.AsyncClient(transport=transport) as client:
                r = await client.get(
                    "http://test/api/v1/products",
                    params={"offset": offset, "limit": limit},
                )
                return r.json()

        return _do()

    with pytest.raises(InvalidInputError):
        await paginate_all(fetch, page_size=100, max_pages=3, results_key="products")


async def test_paginate_all_invalid_page_size() -> None:
    with pytest.raises(InvalidInputError):
        await paginate_all(lambda *_: {}, page_size=0)
    with pytest.raises(InvalidInputError):
        await paginate_all(lambda *_: {}, page_size=200)


async def test_ttl_cache_hit() -> None:
    cache: TTLCache = TTLCache(default_ttl_seconds=60)
    calls = {"n": 0}

    async def compute() -> str:
        calls["n"] += 1
        return f"value-{calls['n']}"

    v1, stale1 = await cache.get_or_compute("k", compute)
    assert v1 == "value-1"
    assert stale1 is False

    v2, stale2 = await cache.get_or_compute("k", compute)
    assert v2 == "value-1"  # pas recalcule
    assert stale2 is False
    assert calls["n"] == 1


async def test_ttl_cache_serves_stale_on_error() -> None:
    cache: TTLCache = TTLCache(default_ttl_seconds=0.01)  # expire vite
    calls = {"n": 0}

    async def compute() -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            return "good"
        raise RuntimeError("fail")

    # Premier appel : stocke "good"
    v1, _ = await cache.get_or_compute("k", compute)
    assert v1 == "good"

    # Attendre l'expiration
    await asyncio.sleep(0.05)

    # Second appel : l'entree est expiree, le recompute echoue,
    # on doit servir "good" stale et l'expiration est repoussee.
    v2, stale = await cache.get_or_compute("k", compute)
    assert v2 == "good"
    assert stale is True


async def test_ttl_cache_concurrent() -> None:
    """Deux appels concurrents ne doublent pas le calcul."""
    cache: TTLCache = TTLCache(default_ttl_seconds=60)
    calls = {"n": 0}

    async def compute() -> str:
        await asyncio.sleep(0.05)
        calls["n"] += 1
        return "v"

    results = await asyncio.gather(
        cache.get_or_compute("k", compute),
        cache.get_or_compute("k", compute),
        cache.get_or_compute("k", compute),
    )
    values = [r[0] for r in results]
    assert values == ["v", "v", "v"]
    assert calls["n"] == 1
