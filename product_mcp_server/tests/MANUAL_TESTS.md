# Manual Tests - Serveur MCP Produit HBntory

Ces tests se font **avec MCP Inspector** (UI web fournie par le SDK MCP).
Ils valident que les outils sont accessibles, leurs schemas corrects, et
que les reponses sont conformes.

## 1. Prerequisites

### 1.1 API Produit externe

```bash
cd ../hbntory-products-api
docker compose up -d
curl http://localhost:5001/health
# -> {"status": "ok"}
```

### 1.2 Serveur MCP en local

```bash
cd product_mcp_server
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env
.venv/bin/python -m src.server
# Logs attendus : "Starting hbntory-product-mcp on 0.0.0.0:8000 ..."
```

Verifier que `/health` repond :
```bash
curl http://localhost:8000/health
# -> {"status": "ok", "service": "hbntory-product-mcp"}
```

## 2. MCP Inspector

Dans un autre terminal :
```bash
cd product_mcp_server
.venv/bin/mcp dev src/server.py
```

L'inspector s'ouvre sur `http://localhost:5173`. Connecter sur
`http://localhost:8000/mcp` (transport Streamable HTTP).

## 3. Tests des outils produit

### 3.1 `list_products` (liste catalogue)

- Appeler l'outil sans parametres.
- **Attendu** : JSON avec cle `products` (tableau non vide) et `total` > 0.
- Re-appeler avec `category="Accessories"`.
- **Attendu** : la liste est filtree sur les accessoires uniquement.
- Re-appeler avec `limit=2, offset=0`.
- **Attendu** : tableau de 2 produits max.

### 3.2 `get_product` (detail)

- Appeler avec `product_id="HB-LAP-1001"`.
- **Attendu** : objet avec `id`, `sku="HB-LAP-1001"`, `name`, `category`, `unit_price`, etc.
- Re-appeler avec `product_id="1"` (forme numerique).
- **Attendu** : meme produit (meme `id=1`).
- Re-appeler avec `product_id="HB-FAUX-9999"`.
- **Attendu** : ToolError "Product not found: HB-FAUX-9999".

### 3.3 `search_products`

- Appeler avec `query="laptop"`.
- **Attendu** : tableau des produits contenant "laptop" (nom ou description).
- Appeler avec `query="zzznotfound"`.
- **Attendu** : tableau vide, pas d'erreur.

## 4. Tests de robustesse

### 4.1 API Produit lente

Arreter puis relancer l'API Produit avec un delai :
```bash
docker compose down
docker compose run -e SIMULATE_DELAY_MS=15000 -p 5001:5000 external-products-api
```

Appeler `list_products` cote MCP Inspector.
**Attendu** : ToolError "External product API unavailable" au bout de 10s
(timeout par defaut du client).

### 4.2 API Produit en erreur

```bash
curl "http://localhost:5001/api/v1/products?force_error=true"
# -> 500
```

Appeler `list_products` cote MCP Inspector.
**Attendu** : ToolError "External product API unavailable".

### 4.3 Validation input

- Appeler `list_products(limit=0)`.
- **Attendu** : erreur de schema (la contrainte `ge=1` est dans le JSON Schema).
- Appeler `search_products(query="")`.
- **Attendu** : erreur de schema (`minLength=1`).
- Appeler `get_product(product_id="foo")`.
- **Attendu** : ToolError "product_id must be numeric or start with 'HB-'".

## 5. Tests des outils Analytics (10 tools, ajoutes apres la Task 4 initiale)

Ces outils lisent le catalogue complet (via l'API Produit) et le stock
(via l'API interne Backoffice) et ne font que de l'agregation en memoire
- aucune ecriture, aucun acces SQL direct.

### 5.1 `analyze_catalog_by_category`

- Appeler sans parametres.
- **Attendu** : cle `categories` avec, pour chaque categorie, nombre de
  produits/prix moyen-min-max/poids total. `products_analyzed` > 0.

### 5.2 `find_extreme_prices`

- Appeler avec `direction="highest", limit=3`.
- **Attendu** : 3 produits les plus chers, tries par prix decroissant.
- Appeler avec `direction="lowest", category="Accessories"`.
- **Attendu** : filtre correctement sur la categorie.
- Appeler avec `direction="foo"`.
- **Attendu** : ToolError ("direction must be 'highest' or 'lowest'").

### 5.3 `find_extreme_weights`

- Appeler avec `direction="heaviest"`.
- **Attendu** : `missing_weight_count` indique combien de produits sans
  poids ont ete exclus (pas juste ignores silencieusement).

### 5.4 `analyze_supplier_portfolio`

- Appeler sans parametres.
- **Attendu** : une entree par fournisseur (nb produits, categories,
  prix moyen, delai, score de fiabilite) - pas de jugement qualitatif
  automatique dans le texte renvoye.

### 5.5 `estimate_catalog_stock_value`

- Appeler sans parametres.
- **Attendu** : valeur totale au **prix catalogue** (pas un cout d'achat
  ni une marge - verifier que la reponse le precise), repartie par
  categorie et par branche.

### 5.6 `assess_storage_complexity`

- Appeler avec `limit=5`.
- **Attendu** : `methodology="heuristic_v1"`, 5 produits avec un
  `complexity_score` (0-100) et le detail des `factors`.

### 5.7 `find_discontinued_with_stock`

- Appeler sans parametres.
- **Attendu** : uniquement des produits `discontinued=true` ET avec
  stock > 0, chacun avec `review_required=true` (jamais de decision
  automatique de liquidation).

### 5.8 `analyze_stock_distribution`

- Appeler sans parametres.
- **Attendu** : repartition par branche + indice de concentration (Gini).

### 5.9 `find_overstocked_products` / 5.10 `find_understocked_products`

- Appeler `find_overstocked_products(threshold_units=50)`.
- **Attendu** : `method="absolute_quantity_threshold"` explicite dans la
  reponse (pas une prevision de demande).
- Meme test pour `find_understocked_products`.

## 6. Tests des outils Forecast (4 tools, P2)

Donnees issues d'un provider **fixture** par defaut (pas d'historique
reel cote Backoffice) - chaque reponse porte `calculation_basis`.

### 6.1 `get_stock_history`

- Appeler avec `product_id="HB-LAP-1001", days=30`.
- **Attendu** : serie de points dates, `calculation_basis` indique
  clairement la source (fixture).

### 6.2 `analyze_stock_trend`

- Appeler avec `product_id="1", days=90`.
- **Attendu** : `direction` (rising/falling/stable), `data_quality`
  (low/medium/high) - pas de "confidence" numerique fabriquee.
- Avec un produit sans historique suffisant (< 3 points) : `data_quality`
  doit tomber a "low", jamais une extrapolation hasardeuse presentee
  comme fiable.

### 6.3 `forecast_stockout_and_reorder`

- Appeler avec `product_id="1", branch_id=1, safety_buffer_days=7`.
- **Attendu** : `estimated_stockout_date` et `recommended_reorder_date`
  accompagnes de `hypotheses` et `limitations` explicites (jamais une
  date presentee sans son incertitude).
- Avec un mouvement moyen nul : les deux dates doivent etre `None`, pas
  une date inventee.

### 6.4 `detect_seasonal_pattern`

- Appeler avec `product_id="1", days=365`.
- **Attendu** : `has_pattern` (bool), `cycles_completed`. Si
  `cycles_completed < 2` : `has_pattern=false` et limitation
  "insufficient_data" explicite plutot qu'un pattern invente.

## 7. Tests des outils Margin (4 tools, P3 - usage interne uniquement)

**Toutes les reponses de cette section doivent porter
`data_origin="synthetic_demo"`** - aucune vraie donnee de vente
n'existe (pas de POS/ERP connecte). A verifier systematiquement.

### 7.1 `compute_product_margin`

- Appeler avec `product_id="1", days=90`.
- **Attendu** : marge brute calculee, `data_origin="synthetic_demo"`
  present dans la reponse.

### 7.2 `identify_most_profitable`

- Appeler avec `metric="gross_margin", limit=5`.
- **Attendu** : top 5 tries par la metrique demandee.
- Appeler avec `metric="foo"`.
- **Attendu** : ToolError ("Unknown metric: foo").

### 7.3 `compute_supplier_cost`

- Appeler avec `days=90`.
- **Attendu** : cout total par fournisseur (achat + transport).

### 7.4 `analyze_storage_efficiency`

- Appeler avec `days=90`.
- **Attendu** : recommandation heuristique par produit
  (keep/review/reduce/drop_candidate) + `warning` rappelant que ce n'est
  **pas** une decision automatique, a valider humainement.

## 8. Checklist de validation

### Outils produit (Task 4 initiale)

- [ ] `/health` repond 200
- [ ] `list_products` (sans filtre) renvoie au moins 1 produit
- [ ] `list_products(category="Accessories")` filtre correctement
- [ ] `get_product("HB-LAP-1001")` renvoie le bon produit
- [ ] `get_product("1")` renvoie le meme produit (forme numerique)
- [ ] `get_product("HB-FAUX-9999")` renvoie ToolError "not found"
- [ ] `search_products("laptop")` renvoie au moins 1 resultat
- [ ] `force_error=true` -> ToolError "unavailable"
- [ ] Validation Pydantic refuse `limit=0` et `query=""`

### Outils Analytics/Forecast/Margin (bonus, au-dela du MVP)

- [ ] `analyze_catalog_by_category` renvoie une agregation coherente
- [ ] `find_extreme_prices` / `find_extreme_weights` filtrent et trient correctement
- [ ] `assess_storage_complexity` renvoie `methodology="heuristic_v1"`
- [ ] `find_discontinued_with_stock` ne renvoie que discontinued + stock > 0
- [ ] `analyze_stock_trend` renvoie `data_quality`, jamais de fausse certitude
- [ ] `forecast_stockout_and_reorder` renvoie `None` plutot qu'une date inventee si donnees insuffisantes
- [ ] Toutes les reponses Margin portent `data_origin="synthetic_demo"`
- [ ] `identify_most_profitable(metric="foo")` renvoie une ToolError claire
