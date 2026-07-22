# Manual Tests — Serveur MCP Produit HBntory

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

## 5. Checklist de validation

- [ ] `/health` repond 200
- [ ] `list_products` (sans filtre) renvoie au moins 1 produit
- [ ] `list_products(category="Accessories")` filtre correctement
- [ ] `get_product("HB-LAP-1001")` renvoie le bon produit
- [ ] `get_product("1")` renvoie le meme produit (forme numerique)
- [ ] `get_product("HB-FAUX-9999")` renvoie ToolError "not found"
- [ ] `search_products("laptop")` renvoie au moins 1 resultat
- [ ] `force_error=true` -> ToolError "unavailable"
- [ ] Validation Pydantic refuse `limit=0` et `query=""`
