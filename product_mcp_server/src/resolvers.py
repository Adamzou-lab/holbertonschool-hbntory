"""Normalisation des identifiants produit (option C).

Regle du projet : la DB du Backoffice stocke des product_id **entiers**.
Mais l'agent IA manipule du texte et va naturellement passer soit un SKU
('HB-LAP-1001'), soit un identifiant numerique en string ('1').

Ce module fait la traduction :
  - '1'        -> 1  (numerique direct)
  - 'HB-LAP-1001' -> 1  (resolution via l'API Produit externe, puis on garde l'id)
  - autres formes -> ResolverError

Toutes les fonctions sont async pour permettre le cache async futur.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from .errors import ProductApiError, ResolverError

if TYPE_CHECKING:
    from .product_client import ProductClient

logger = logging.getLogger(__name__)


def _is_int_string(s: str) -> bool:
    """Vrai si la chaine represente un entier positif."""
    if not s:
        return False
    if not s.isdigit():
        return False
    return True


async def resolve_product_id(
    raw: str,
    product_client: ProductClient,
) -> int:
    """Convertit une representation textuelle en identifiant entier.

    Strategie :
      1. Si la chaine est numerique : on l'utilise directement (apres check >= 1).
      2. Si elle commence par 'HB-' (format SKU) : on demande a l'API externe
         de resoudre le SKU en produit, puis on prend son champ `id` (entier).
      3. Sinon : ResolverError avec un message clair pour l'agent.

    Raises:
        ResolverError: si la forme est invalide.
        ProductApiError: si la resolution SKU echoue cote API externe.
    """
    if raw is None:
        raise ResolverError("product_id must not be empty.")

    s = str(raw).strip()
    if not s:
        raise ResolverError("product_id must not be empty.")

    # Cas numerique direct
    if _is_int_string(s):
        pid = int(s)
        if pid < 1:
            raise ResolverError(f"product_id must be >= 1, got {pid}")
        return pid

    # Cas SKU : on resout via l'API externe (insensible a la casse)
    if s.upper().startswith("HB-"):
        sku = s.upper()
        try:
            product = await product_client.get(sku)
        except ProductApiError as exc:
            # On remonte en ResolverError pour que to_tool_error produise
            # un message coherent cote agent.
            raise ResolverError(
                f"Cannot resolve product_id {s!r}: {exc}"
            ) from exc
        pid = product.get("id")
        if not isinstance(pid, int) or pid < 1:
            raise ResolverError(
                f"Resolved SKU {sku!r} returned invalid id: {pid!r}"
            )
        return pid

    raise ResolverError(
        f"product_id must be numeric or start with 'HB-': got {s!r}"
    )


# --- Cache LRU simple (async-safe via lock) ---

_sku_cache: dict[str, int] = {}
_sku_cache_lock = asyncio.Lock()
_SKU_CACHE_MAX = 256


async def resolve_product_id_cached(
    raw: str,
    product_client: ProductClient,
) -> int:
    """Comme resolve_product_id, mais avec un cache LRU en memoire.

    Le cache est limite a 256 entrees (FIFO eviction pour rester simple).
    Cible : eviter de re-resoudre le meme SKU quand l'agent enchaîne
    plusieurs appels outils sur le meme produit.
    """
    s = str(raw).strip()
    if s.upper().startswith("HB-"):
        async with _sku_cache_lock:
            if s in _sku_cache:
                return _sku_cache[s]
    pid = await resolve_product_id(raw, product_client)
    if s.upper().startswith("HB-"):
        async with _sku_cache_lock:
            if len(_sku_cache) >= _SKU_CACHE_MAX:
                # FIFO eviction : on jette la plus ancienne
                _sku_cache.pop(next(iter(_sku_cache)))
            _sku_cache[s] = pid
    return pid


def clear_sku_cache() -> None:
    """Vide le cache (utile pour les tests)."""
    _sku_cache.clear()
