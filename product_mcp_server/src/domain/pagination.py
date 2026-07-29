"""Pagination robuste des endpoints pagines (API Produit).

Protege contre les boucles infinies et les repetitions silencieuses.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from ..errors import InvalidInputError

logger = logging.getLogger(__name__)

DEFAULT_MAX_PAGES = 20
DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 100


async def paginate_all(
    fetch_page: Callable[[int, int], Awaitable[dict[str, Any]]],
    *,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_pages: int = DEFAULT_MAX_PAGES,
    results_key: str = "products",
    extra_query_params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Recupere toutes les pages en evitant les boucles infinies.

    Args:
        fetch_page: async (offset, limit) -> dict avec cle ``results_key``.
        page_size: taille de page (bornee par MAX_PAGE_SIZE).
        max_pages: garde-fou ; leve InvalidInputError si depasse.
        results_key: cle de la liste dans la reponse API.
        extra_query_params: non utilise ici (utile si wrappez en amont).

    Returns:
        Liste agregee des items de toutes les pages.

    Raises:
        InvalidInputError: si pagination bloquée par garde-fou.
        ProductApiError: si l'API echoue.
    """
    if page_size < 1 or page_size > MAX_PAGE_SIZE:
        raise InvalidInputError(f"page_size must be in 1..{MAX_PAGE_SIZE}, got {page_size}")

    all_items: list[dict[str, Any]] = []
    seen_keys: set[Any] = set()
    offset = 0
    pages = 0

    while pages < max_pages:
        page = await fetch_page(offset, page_size)
        items = page.get(results_key, []) or []
        if not items:
            break
        for item in items:
            key = item.get("sku") or item.get("id")
            if key in seen_keys:
                logger.warning(
                    "Duplicate item detected in pagination at offset=%d (key=%s) — stopping.",
                    offset,
                    key,
                )
                return all_items
            seen_keys.add(key)
            all_items.append(item)
        if len(items) < page_size:
            break
        offset += page_size
        pages += 1

    if pages >= max_pages and offset > 0:
        raise InvalidInputError(
            f"Pagination hit max_pages={max_pages} safety limit. "
            f"Increase max_pages or check upstream pagination consistency."
        )

    return all_items


__all__ = ["paginate_all", "DEFAULT_MAX_PAGES", "DEFAULT_PAGE_SIZE"]
