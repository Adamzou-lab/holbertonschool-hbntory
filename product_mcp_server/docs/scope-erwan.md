# Perimetre Erwan — `product_mcp_server/` (Bloc 2)

Document d'engagement de perimetre. Tout commit sur `erwan` doit etre
verifie contre cette liste.

## Dossiers autorises

```
product_mcp_server/**
```

## Dossiers interdits (ne JAMAIS modifier)

```
backoffice/**
client_web/**
database/**
migrations/**
docker-compose.yml racine
README.md racine
scripts globaux de l'equipe
config CI commune
```

## Fichiers existants a ne pas modifier (backoffice / client_web)

```
backoffice/models.py        # Schema SQLAlchemy
backoffice/auth.py          # Authentification
backoffice/decorators.py    # Roles
backoffice/stock_service.py # Validation stock
backoffice/app.py           # Routes Flask
backoffice/seed.py          # Seed DB
backoffice/requirements.txt
```

## Tests initiaux (baseline)

Avant toute modification :

```bash
cd product_mcp_server
.venv/bin/pytest -v
```

Resultat attendu : 85 tests passants (37 legacy + 48 nouveaux).

## Liste des 7 tools MCP existants

1. `list_products`
2. `get_product`
3. `search_products`
4. `list_branches`
5. `get_product_availability`
6. `get_branch_inventory`
7. `check_shopping_list`

Voir `docs/tools.md` pour la liste complete des 25 tools.