"""Cache TTL async-safe pour resultats lourds (catalogue complet, fournisseurs).

Politique :
- TTL configurable (defaut 300s).
- Verrou asyncio par cle pour eviter le dog-pile.
- Resultat perime signale (``served_stale=True`` dans la valeur retournee).
- Pas de Redis / pas d'infra externe.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class CacheEntry:
    value: Any
    expires_at: float
    created_at: float


class TTLCache:
    """Cache memoire async-safe avec expiration."""

    def __init__(self, default_ttl_seconds: float = 300.0) -> None:
        self._ttl = default_ttl_seconds
        self._store: dict[str, CacheEntry] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    def _now(self) -> float:
        return time.monotonic()

    async def get_or_compute(
        self,
        key: str,
        compute: Callable[[], Awaitable[T]],
        *,
        ttl: float | None = None,
    ) -> tuple[T, bool]:
        """Renvoie (valeur, served_stale).

        ``served_stale=True`` signifie qu'on a utilise la valeur perimee parce
        que le recalcul a echoue. Le caller peut decider de le signaler au LLM.

        Politique :
        - Cache valide : renvoyer direct.
        - Cache expire present : on tente le refresh ; si echec, on sert la valeur stale.
        - Cache absent : on calcule ; si echec, on propage.
        """
        ttl = ttl if ttl is not None else self._ttl
        now = self._now()
        entry = self._store.get(key)

        if entry is not None and entry.expires_at > now:
            return entry.value, False

        lock = await self._get_lock(key)
        async with lock:
            entry = self._store.get(key)
            if entry is not None and entry.expires_at > now:
                return entry.value, False

            try:
                value = await compute()
            except Exception:
                if entry is not None:
                    # L'ancienne valeur est perimee mais on la sert.
                    logger.warning(
                        "Cache recompute failed for key=%s, serving stale value.", key
                    )
                    # On etend l'expiration pour eviter de re-tenter immediatement.
                    self._store[key] = CacheEntry(
                        value=entry.value,
                        expires_at=now + ttl,
                        created_at=entry.created_at,
                    )
                    return entry.value, True
                raise

            self._store[key] = CacheEntry(
                value=value, expires_at=self._now() + ttl, created_at=self._now()
            )
            return value, False

    async def _get_lock(self, key: str) -> asyncio.Lock:
        async with self._global_lock:
            lock = self._locks.get(key)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[key] = lock
            return lock

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()


# Cache partage pour le catalogue complet
CATALOG_CACHE = TTLCache(default_ttl_seconds=300.0)
SUPPLIERS_CACHE = TTLCache(default_ttl_seconds=600.0)


__all__ = ["TTLCache", "CATALOG_CACHE", "SUPPLIERS_CACHE"]
