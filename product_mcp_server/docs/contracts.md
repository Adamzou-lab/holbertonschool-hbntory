# Contrats et frontieres du serveur MCP HBntory

Ce document precise les interfaces entre le serveur MCP et ses sources
de donnees externes. Il sert de reference pour les Boundary Tests (ADR-E08).

## 1. API Produit externe

Base : `settings.products_api_base_url` (defaut `http://localhost:5001`).

| Endpoint | Usage MCP | Notes |
|---|---|---|
| `GET /health` | Verification demarrage | Pas appele par les outils |
| `GET /api/v1/products?limit&offset&category&supplier_id&include_discontinued` | `list_products`, `analyze_*` (via cache + pagination) | Reponse : `{products, total, limit, offset}` |
| `GET /api/v1/products/{sku_or_id}` | `get_product`, `analyze_*` (resolution SKU -> id) | Accepte SKU `HB-LAP-1001` ou id numerique |
| `GET /api/v1/products/search?q&limit` | `search_products` | |
| `GET /api/v1/suppliers` | `analyze_supplier_portfolio` | Optionnel : si non disponible, le tool fonctionne avec les donnees du catalogue uniquement |

### Format produit

```json
{
  "id": 1,
  "sku": "HB-LAP-1001",
  "name": "Holberton Student Laptop 14",
  "category": "Laptops",
  "brand": "Holberton",
  "supplier_id": "SUP-HBT-001",
  "supplier_name": "Holberton Tools Co.",
  "unit_price": 799.0,
  "currency": "USD",
  "discontinued": false,
  "weight_kg": 1.35,
  "tags": ["student", "portable", "linux-ready"],
  "updated_at": "2026-05-22T12:00:00Z"
}
```

## 2. API interne Backoffice

Base : `settings.backoffice_base_url` (defaut `http://localhost:5000`).

Header obligatoire : `X-Internal-Token: <shared_secret>`.

| Endpoint | Usage MCP |
|---|---|
| `GET /api/internal/branches` | `list_branches` |
| `GET /api/internal/stock/by-product/<int:product_id>` | `get_product_availability` |
| `GET /api/internal/stock/by-branch/<int:branch_id>` | `get_branch_inventory` |
| `POST /api/internal/stock/shopping-list` | `check_shopping_list` |

### Format stock par produit

```json
[
  {"branch_id": 1, "branch_name": "Paris", "quantity": 50},
  {"branch_id": 2, "branch_name": "Lyon", "quantity": 5}
]
```

### Format shopping-list response

```json
{
  "branches": [
    {
      "branch_id": 1,
      "branch_name": "Paris",
      "items": [
        {"product_id": 1, "requested": 3, "available": 50, "satisfied": true}
      ],
      "missing": []
    }
  ],
  "strategy": "single" | "split",
  "recommendation": "..."
}
```

## 3. Providers Forecast (Phase 2)

Interface `ForecastDataProvider` :

```python
class ForecastDataProvider(Protocol):
    async def get_history(
        self,
        *,
        product_id: int,
        branch_id: int | None,
        days: int,
    ) -> list[StockHistoryPoint]: ...
```

### Implementations

- `FixtureForecastProvider` : serie deterministe (seed = `product_id|branch_id|fixture_v1`).
  Genere ~30-90 jours avec sinusoide + bruit. Pas de dependance externe.
- `HttpForecastProvider` : HTTP vers `/api/internal/forecast/history?product_id&branch_id&days`.
  Si 404 (route absente), leve `StockApiError("endpoint not available")` ; les tools
  peuvent catcher et basculer en fixture si besoin futur.

## 4. Providers Profitabilite (Phase 3)

Interface `ProfitabilityDataProvider` :

```python
class ProfitabilityDataProvider(Protocol):
    async def get_events(
        self,
        *,
        days: int,
        seed: int | None = None,
    ) -> ProfitabilityData: ...
```

### Implementation unique : `FixtureProfitabilityProvider`

- Genere 3*days ventes (~540 pour 180 jours) et max(20, days/2) achats.
- Deterministe : meme seed = meme dataset.
- Toutes les valeurs en `Decimal`.
- Toutes les evenements ont `data_origin="synthetic_demo"`.
- Aucune route reelle attendue cote Backoffice : pas de dependance externe.

## 5. Garanties aux frontieres

- Validation Pydantic de toutes les reponses HTTP (echec = `InvalidUpstreamResponse`).
- Retry sur 429/5xx/timeout (1 tentative supplementaire max).
- Timeout 10s par defaut (configurable).
- Mapping strict des erreurs HTTP en `ErrorCode` normalises.
- Aucune stack trace dans les reponses envoyees au LLM.

## 6. Limitations documentees

- Les providers Forecast et Profitabilite n'ont **aucune** source reelle cote Backoffice.
  Ce sont des fixtures deterministes ; toute prediction est indicative, pas un calcul
  economique reel.
- Le serveur MCP ne sait pas distinguer une "vraie vente" d'une simple baisse de stock :
  `forecast_stockout_and_reorder` parle de "movement" (delta), pas de "sales".
- Les recommandations `storage_efficiency` (keep/review/reduce/drop_candidate) sont des
  heuristiques NON automatiques, a valider humainement.