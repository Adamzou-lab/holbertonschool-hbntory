# Manual Tests — Service IA HBntory

Tests bout-en-bout : serveur MCP (Bloc 2) + Service IA (Bloc 3) + un vrai provider LLM.
Ces tests **nécessitent une clé API** (`ANTHROPIC_API_KEY` par défaut, ou autre).

## 1. Prérequis

### 1.1 Lancer l'API Produit externe

```bash
cd ../hbntory-products-api
docker compose up -d
curl http://localhost:5001/health
# -> {"status": "ok"}
```

### 1.2 Lancer le serveur MCP (Bloc 2, déjà livré sur `erwan`)

```bash
cd ../product_mcp_server
.venv/bin/python -m src.server
# Log : "Starting hbntory-product-mcp on 0.0.0.0:8000 ..."
curl http://localhost:8000/health
# -> {"status": "ok", "service": "hbntory-product-mcp"}
```

### 1.3 Lancer le Service IA

```bash
cd ai_service
cp .env.example .env
# Editer .env : mettre votre cle API
#   ANTHROPIC_API_KEY=sk-ant-...
.venv/bin/python -m src.main
# Log : "HBntory AI Service ready on 0.0.0.0:8080"
```

## 2. Sanity checks (sans LLM)

### 2.1 `/health`

```bash
curl -s http://localhost:8080/health | jq
```

Attendu : `status: "ok"`, `service: "hbntory-ai-service"`, `mcp_server_url` et
`llm_provider` / `llm_model` renseignés.

### 2.2 `/tools`

```bash
curl -s http://localhost:8080/tools | jq
```

Attendu : tableau de **25 outils** — les 7 d'origine (inventaire :
`list_products`, `get_product`, `search_products`, `list_branches`,
`get_product_availability`, `get_branch_inventory`, `check_shopping_list`)
plus 18 ajoutés depuis (10 analytics, 4 forecast, 4 margin — voir §3.5 à
3.7). `/tools` liste tout ce que le MCP expose ; chaque agent spécialisé
ne voit ensuite qu'un sous-ensemble filtré (allowlist par intent, voir
`ai_service/docs/agents.md`).

### 2.3 Swagger UI

Ouvrir `http://localhost:8080/docs` dans un navigateur. La spec OpenAPI
doit lister `/query`, `/health`, `/tools` avec leurs schémas.

## 3. Tests des 4 types de questions du sujet

> Chaque appel prend quelques secondes (latence LLM). Patienter.

### 3.1 Détail produit

```bash
curl -s -X POST http://localhost:8080/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Donne-moi les details du produit HB-LAP-1001"}' | jq
```

Attendu :
- `answer` contient le nom, la catégorie, le prix, etc.
- `tool_calls` contient au moins `get_product`.

### 3.2 Où est disponible un produit

```bash
curl -s -X POST http://localhost:8080/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Dans quelle branche puis-je trouver le Holberton Student Laptop 14 ?"}' | jq
```

Attendu :
- `answer` cite au moins une branche avec une quantité.
- `tool_calls` contient `search_products` puis `get_product_availability` (ou directement `get_product_availability`).

### 3.3 Contenu d'une branche

```bash
curl -s -X POST http://localhost:8080/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Quels produits sont en stock dans la branche Paris ?"}' | jq
```

Attendu :
- `answer` liste des produits avec quantités.
- `tool_calls` contient `list_branches` puis `get_branch_inventory`.

### 3.4 Shopping list multi-produits

```bash
curl -s -X POST http://localhost:8080/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Si je veux 3 HB-LAP-1001 et 2 HB-MON-2101, dans quelle branche aller ?"}' | jq
```

Attendu :
- `answer` propose une ou plusieurs branches avec détail satisfait / manquant.
- `tool_calls` contient `check_shopping_list` (et probablement `get_product` pour valider les SKU).

### 3.5 Analytics (routage vers l'agent "analytics")

```bash
curl -s -X POST http://localhost:8080/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Quels sont les 3 produits les plus chers du catalogue ?"}' | jq
```

Attendu :
- `intent: "analytics"`, `routing_confidence` renseigné.
- `tool_calls` contient `find_extreme_prices`.
- `answer` précise que c'est le **prix catalogue**, pas une valeur de
  stock ni une marge (le system prompt Analytics l'impose).

### 3.6 Forecast (routage vers l'agent "forecast")

```bash
curl -s -X POST http://localhost:8080/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Quand le laptop 14 pouces risque-t-il d'\''etre en rupture ?"}' | jq
```

Attendu :
- `intent: "forecast"`.
- `tool_calls` contient `forecast_stockout_and_reorder` (et probablement
  `get_stock_history`/`analyze_stock_trend` en amont).
- `answer` mentionne explicitement l'incertitude (`data_quality`,
  hypothèses) — jamais une date affirmée sans nuance.

### 3.7 Margin — endpoint interne uniquement (`/internal/query`)

Nécessite `AI_INTERNAL_TOKEN` configuré (`.env`, absent par défaut —
sans lui l'endpoint renvoie 503 volontairement, voir §4.5).

```bash
curl -s -X POST http://localhost:8080/internal/query \
  -H "Content-Type: application/json" \
  -H "X-Internal-Token: $AI_INTERNAL_TOKEN" \
  -d '{"question": "Quels sont les produits les plus rentables ?"}' | jq
```

Attendu :
- `intent: "margin"`.
- `data_origins` contient `"synthetic_demo"`.
- `answer` rappelle explicitement que ce sont des données synthétiques
  de démonstration, pas de vraies ventes.
- **Vérifier aussi que `/query` (public) refuse cette même question** —
  doit répondre que les analyses de rentabilité sont réservées à l'usage
  interne, sans jamais exécuter `compute_product_margin` côté public.

## 4. Tests de robustesse

### 4.1 Question hors périmètre

```bash
curl -s -X POST http://localhost:8080/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Quel temps fait-il a Paris aujourd'\''hui ?"}' | jq
```

Attendu : `answer` contient un refus poli du type
« Je suis spécialisé dans l'inventaire HBntory... ».

### 4.2 Produit inexistant

```bash
curl -s -X POST http://localhost:8080/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Donne-moi les details du produit HB-FAUX-9999"}' | jq
```

Attendu : `answer` dit explicitement que le produit n'existe pas / n'est pas trouvé.

### 4.3 Question vide

```bash
curl -s -X POST http://localhost:8080/query \
  -H "Content-Type: application/json" \
  -d '{"question": ""}' -w "\nHTTP %{http_code}\n"
```

Attendu : HTTP 422 (validation Pydantic).

### 4.4 MCP down

Couper le serveur MCP (`Ctrl+C` côté `product_mcp_server`).
Relancer une requête :

```bash
curl -s -X POST http://localhost:8080/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Ou est le laptop ?"}' -w "\nHTTP %{http_code}\n"
```

Attendu : HTTP 503 « Inventory service temporarily unavailable. »
(Note : la connexion MCP du Service IA peut mettre quelques secondes à
s'apercevoir de la coupure selon le timeout MCP configuré.)

### 4.5 `/internal/query` sans jeton configuré

Sans `AI_INTERNAL_TOKEN` dans l'environnement (cas par défaut du
`docker-compose.yml` actuel — variable non câblée) :

```bash
curl -s -X POST http://localhost:8080/internal/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Marge la plus elevee ?"}' -w "\nHTTP %{http_code}\n"
```

Attendu : HTTP 503 « Internal endpoint not configured. » — fermé par
défaut plutôt qu'ouvert sans protection (voir `src/security.py`).

### 4.6 `/internal/query` avec un mauvais jeton

`AI_INTERNAL_TOKEN` configuré, mais header manquant ou incorrect :

```bash
curl -s -X POST http://localhost:8080/internal/query \
  -H "Content-Type: application/json" \
  -H "X-Internal-Token: mauvais-token" \
  -d '{"question": "Marge la plus elevee ?"}' -w "\nHTTP %{http_code}\n"
```

Attendu : HTTP 401 « Invalid or missing X-Internal-Token. »

## 5. Test d'observabilité des tool calls

Vérifier que **chaque** réponse de l'agent qui touche à un fait concret
contient au moins un `tool_calls` non vide. C'est ce qui prouve au jury
que l'agent s'appuie sur les outils, pas sur son imagination.

```bash
# Compteur rapide : nombre de tool_calls par question
for q in "Quel est le laptop 14 ?" "Stock a Lyon ?" "Liste des produits"; do
  count=$(curl -s -X POST http://localhost:8080/query \
    -H "Content-Type: application/json" \
    -d "{\"question\": \"$q\"}" | jq '.tool_calls | length')
  echo "$q -> $count tool calls"
done
```

Attendu : `>= 1` pour chaque question portant sur l'inventaire.

## 6. Checklist de validation finale

### Périmètre initial (7 outils, inventaire)

- [ ] `/health` répond 200
- [ ] `/tools` liste les 25 outils MCP (7 inventaire + 18 bonus)
- [ ] `/query` 4 questions types → réponses grounded + tool_calls présents
- [ ] Question hors périmètre → refus poli
- [ ] Produit inexistant → « non trouvé »
- [ ] Question vide → 422
- [ ] MCP down → 503
- [ ] Logs serveur IA : chaque appel de tool est loggué (utile pour la démo)

### Multi-agent et outils bonus (analytics/forecast/margin)

- [ ] Question analytics → `intent: "analytics"`, tool correspondant appelé
- [ ] Question forecast → `intent: "forecast"`, réponse nuancée (jamais de date affirmée sans hypothèses)
- [ ] Question margin sur `/query` (public) → refusée, `tool_calls` vide
- [ ] Question margin sur `/internal/query` avec bon jeton → répond, `data_origins` contient `"synthetic_demo"`
- [ ] `/internal/query` sans jeton configuré → 503
- [ ] `/internal/query` avec mauvais jeton → 401
