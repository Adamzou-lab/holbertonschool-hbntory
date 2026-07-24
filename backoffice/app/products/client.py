"""Client vers l'API Produit externe (lecture seule, fournie en Docker).

Résout un product_id (l'id numérique interne — même référentiel que celui
attendu par /api/v1/products/{id}, cf. product_mcp_server/src/resolvers.py
"option C") en nom/catégorie pour l'affichage côté Backoffice.

Règle d'or du projet : ces données ne sont jamais stockées en base
(docs/architecture.md §3). Le cache mémoire ci-dessous a une durée de vie
courte et sert uniquement à éviter de rappeler l'API à chaque rendu de
page stock — ce n'est pas une persistance des données produit.

Ne lève jamais d'exception : une page de stock ne doit pas planter parce
que l'API Produit est en panne ou qu'un produit a été supprimé côté
catalogue, elle doit juste afficher un nom indisponible pour ce produit-là.
"""

from __future__ import annotations

import time

import requests
from flask import current_app

from app import settings

_CACHE_TTL_SECONDS = 60
_cache = {}


def get_product(product_id):
    cached = _cache.get(product_id)
    if cached is not None and time.time() - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    # L'admin peut surcharger l'URL à chaud depuis /admin/settings ; sinon
    # on retombe sur la variable d'environnement (app.config).
    base_url = settings.get_setting(
        settings.PRODUCTS_API_BASE_URL,
        default=current_app.config["PRODUCTS_API_BASE_URL"],
    )
    try:
        resp = requests.get(
            f"{base_url}/api/v1/products/{product_id}", timeout=3
        )
        product = resp.json() if resp.status_code == 200 else None
    except requests.RequestException:
        current_app.logger.warning(
            "API Produit injoignable pour product_id=%s", product_id
        )
        product = None

    _cache[product_id] = (time.time(), product)
    return product


def get_products(product_ids):
    """Résout plusieurs product_id d'un coup (dédupliqués).

    Retourne {product_id: dict | None} — None pour ceux introuvables ou
    si l'API était injoignable au moment de l'appel.
    """
    return {pid: get_product(pid) for pid in set(product_ids)}


_CATALOG_CACHE_TTL_SECONDS = 60
_catalog_cache = None


def list_catalog():
    """Liste complète du catalogue (pour peupler un menu déroulant côté
    "Ajouter du stock"), triée par nom. [] si l'API est injoignable —
    le formulaire retombe alors sur la saisie manuelle de l'id.
    """
    global _catalog_cache
    if _catalog_cache is not None and (
        time.time() - _catalog_cache[0] < _CATALOG_CACHE_TTL_SECONDS
    ):
        return _catalog_cache[1]

    base_url = settings.get_setting(
        settings.PRODUCTS_API_BASE_URL,
        default=current_app.config["PRODUCTS_API_BASE_URL"],
    )
    products = []
    try:
        resp = requests.get(
            f"{base_url}/api/v1/products",
            params={"limit": 100, "offset": 0},
            timeout=3,
        )
        if resp.status_code == 200:
            products = resp.json().get("results", [])
    except requests.RequestException:
        current_app.logger.warning("API Produit injoignable pour la liste")

    products.sort(key=lambda p: p.get("name", ""))
    _catalog_cache = (time.time(), products)
    return products
