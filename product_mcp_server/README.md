# HBntory Product MCP Server

Serveur MCP (Model Context Protocol) qui sert de **pont** entre le Service IA
et deux sources de données :

1. **L'API Produit externe** ([hbntory-products-api](https://github.com/hbtn-edu/hbntory-products-api)),
   fournie en Docker, lecture seule - source unique des informations catalogue.
2. **L'API interne du Backoffice HBntory**, lecture seule - pour les consultations
   de stock (quantités par branche).

> Bloc 2 du projet HBntory. Aucune dépendance vers `backoffice/` (Flask/SQLAlchemy)
> ni vers `ai_service/` / `client_web/`. Le MCP est un service strictement isolé.

## Outils MCP exposés (7 au total)

### Produits (3) - via API externe

| Tool | Description | Input |
|---|---|---|
| `list_products` | Liste paginée du catalogue avec filtres (catégorie, fournisseur, pagination) | `category?`, `supplier_id?`, `include_discontinued?=false`, `limit?=20`, `offset?=0` |
| `get_product` | Détail d'un produit (nom, prix, description, etc.) | `product_id: str` (SKU `HB-...` ou numérique `1`) |
| `search_products` | Recherche textuelle (nom, SKU, description, tags) | `query: str`, `limit?=10` |

### Stock (4, lecture seule) - via API interne Backoffice

| Tool | Description | Input |
|---|---|---|
| `list_branches` | Liste des branches HBntory (id + nom) | – |
| `get_product_availability` | Branches qui ont du stock d'un produit + quantités | `product_id: str` |
| `get_branch_inventory` | Produits en stock dans une branche | `branch_id: int` |
| `check_shopping_list` | Meilleure(s) branche(s) pour une liste d'achat | `items: [{product_id, quantity}, ...]` |

**Aucun outil n'écrit dans le stock.** Les mutations (add/remove) restent dans
le Backoffice, derrière authentification + rôles. Justification : le client web
qui déclenche les appels IA est anonyme, sans session ni rôle - laisser l'IA
muter contournerait toute la sécurité du projet.

## Option C : normalisation des `product_id`

Les LLM passent naturellement du texte dans leurs appels. Le MCP accepte donc
deux formes :

| Forme reçue | Traitement | Sortie (vers API Backoffice) |
|---|---|---|
| `"1"` | numérique direct | `1` (int) |
| `"HB-LAP-1001"` | résolution via API externe | `1` (int) - l'`id` retourné |
| `"hb-lap-1001"` | idem, insensible à la casse | `1` (int) |
| `"foo"` | refus | – |

Aucun impact sur la DB du Backoffice (qui reste en `Integer`), aucun impact
sur le code des collègues. Le MCP fait la traduction en interne.

## Installation locale

```bash
cd product_mcp_server
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env
# editer .env si besoin (URLs API Produit + Backoffice, token partage)
.venv/bin/python -m src.server
```

Le serveur écoute sur `http://localhost:8000` :

```bash
curl http://localhost:8000/health
# {"status": "ok", "service": "hbntory-product-mcp"}
```

## Lancement Docker

```bash
docker build -t hbntory-product-mcp ./product_mcp_server
docker run --rm -p 8000:8000 \
  -e PRODUCTS_API_BASE_URL=http://host.docker.internal:5001 \
  -e BACKOFFICE_BASE_URL=http://host.docker.internal:5000 \
  -e BACKOFFICE_INTERNAL_TOKEN=change-me-shared-secret \
  hbntory-product-mcp
```

## Tests

```bash
.venv/bin/pytest -v
```

37 tests couvrent :
- Résolveur (12 cas : numérique, SKU, casse, cache, etc.)
- Outils produit (9 cas : filtres, schéma, 404, 500)
- Outils stock (16 cas : header `X-Internal-Token`, 403, 404, 500, satisfaction partielle / totale)

Les tests utilisent `httpx.MockTransport` - aucune connexion réseau requise.

## Tests manuels via MCP Inspector

Voir [`tests/MANUAL_TESTS.md`](tests/MANUAL_TESTS.md).

## Variables d'environnement

| Variable | Défaut | Rôle |
|---|---|---|
| `PRODUCTS_API_BASE_URL` | `http://localhost:5001` | URL de l'API Produit externe |
| `BACKOFFICE_BASE_URL` | `http://localhost:5000` | URL de l'API interne du Backoffice |
| `BACKOFFICE_INTERNAL_TOKEN` | `change-me` | Token partagé envoyé en `X-Internal-Token` |
| `MCP_HOST` | `0.0.0.0` | Host d'écoute du serveur MCP |
| `MCP_PORT` | `8000` | Port d'écoute |
| `LOG_LEVEL` | `INFO` | Niveau de log |
| `REQUEST_TIMEOUT_SECONDS` | `10` | Timeout HTTP sortant |

## Contrat de l'API interne attendu côté Backoffice

À livrer par Nico (`backoffice/app.py`) - header `X-Internal-Token` requis :

| Méthode | Path | Réponse |
|---|---|---|
| `GET` | `/api/internal/branches` | `[{id, name}]` |
| `GET` | `/api/internal/stock/by-product/<int:product_id>` | `[{branch_id, branch_name, quantity}]` |
| `GET` | `/api/internal/stock/by-branch/<int:branch_id>` | `[{product_id, quantity}]` |
| `POST` | `/api/internal/stock/shopping-list` | `{branches: [{branch_id, branch_name, items, missing}], strategy, recommendation}` |
| `GET` | `/api/internal/health` | `{status: "ok"}` |

## Arborescence

```
product_mcp_server/
├── Dockerfile
├── README.md
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── .env.example
├── .dockerignore
├── src/
│   ├── __init__.py
│   ├── config.py             # pydantic-settings
│   ├── errors.py             # exceptions + mapping ToolError
│   ├── product_client.py     # httpx -> API Produit
│   ├── stock_client.py       # httpx -> API interne Backoffice
│   ├── resolvers.py          # option C : string|int -> int
│   ├── server.py             # FastMCP + /health + entrypoint
│   └── tools/
│       ├── product_tools.py  # 3 outils catalogue
│       └── stock_tools.py    # 4 outils stock (read-only)
└── tests/
    ├── conftest.py
    ├── test_resolvers.py
    ├── test_product_tools.py
    ├── test_stock_tools.py
    └── MANUAL_TESTS.md
```

## Choix techniques résumés

| Décision | Valeur | Justification |
|---|---|---|
| Transport MCP | Streamable HTTP via FastMCP | Service indépendant, conteneur séparé (cf. `docs/decisions.md`) |
| `mcp` SDK | `mcp[cli]>=1.2` (FastMCP natif) | SDK officiel Python, ASGI, support JSON Schema auto |
| Client HTTP | `httpx` async | `MockTransport` pour tester sans réseau |
| Validation | `pydantic>=2.6` + Pydantic Settings | Contraintes déclaratives sur les inputs outils |
| Lecture stock | API interne Backoffice (token) | Frontière respectée : MCP ne touche pas la DB |
| Mutations stock | **Aucune** | L'agent sert un user anonyme, sécurité du projet |
| Type `product_id` | string côté MCP, int côté DB | Option C : MCP résout en interne, zéro impact ailleurs |

## Limites connues

- L'API externe `hbntory-products-api` doit être accessible sur `localhost:5001`
  (ou via `PRODUCTS_API_BASE_URL`). Si elle est down, les outils produit
  renvoient `"External product API unavailable"` (timeout 10s).
- L'API interne du Backoffice n'est **pas encore livrée** par Nico. Les outils
  stock sont implémentés et testés en mock ; leur validation bout-en-bout
  attend la livraison des routes `/api/internal/...`.
- Pas de streaming de réponse : le MCP renvoie la réponse complète d'un coup
  (le transport Streamable HTTP gère les sessions mais chaque tool reste
  request/response).
