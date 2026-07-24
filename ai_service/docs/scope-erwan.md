# Perimetre Erwan — `ai_service/` (Bloc 3 cote IA)

Document d'engagement de perimetre. Tout commit sur `erwan` doit etre
verifie contre cette liste.

## Dossiers autorises

```
ai_service/**
```

## Dossiers interdits (ne JAMAIS modifier)

```
backoffice/**
client_web/**
product_mcp_server/         # base du Bloc 2, gere par Erwan dans un autre commit
docker-compose.yml racine
README.md racine
scripts globaux de l'equipe
config CI commune
```

## Tests initiaux (baseline)

Avant toute modification :

```bash
cd ai_service
.venv/bin/pytest -v
```

Resultat attendu : 127 tests passants.

## Endpoints exposes

| Endpoint | Methode | Auth | Intents autorises |
|---|---|---|---|
| `/health` | GET | non | (probe) |
| `/tools` | GET | non (gated par `expose_tools_endpoint`) | (debug) |
| `/query` | POST | non | inventory, analytics, forecast |
| `/internal/query` | POST | `X-Internal-Token: $AI_INTERNAL_TOKEN` | inventory, analytics, forecast, margin |
| `/docs`, `/openapi.json` | GET | non | (Swagger) |

## Architecture des 4 agents

| Agent | Tools autorises (allowlist reelle) | Endpoint |
|---|---|---|
| Inventory | 7 tools : list_products, get_product, search_products, list_branches, get_product_availability, get_branch_inventory, check_shopping_list | `/query` + `/internal/query` |
| Analytics | 10 tools : analyze_catalog_by_category, find_extreme_prices, find_extreme_weights, analyze_supplier_portfolio, estimate_catalog_stock_value, assess_storage_complexity, find_discontinued_with_stock, analyze_stock_distribution, find_overstocked_products, find_understocked_products | `/query` + `/internal/query` |
| Forecast | 4 tools : get_stock_history, analyze_stock_trend, forecast_stockout_and_reorder, detect_seasonal_pattern | `/query` + `/internal/query` |
| Margin | 4 tools : compute_product_margin, identify_most_profitable, compute_supplier_cost, analyze_storage_efficiency | `/internal/query` uniquement |

## Routage

Architecture hybride :
1. Regles deterministes (mots-cles) -> intent certain
2. Si ambigu : routeur LLM (PydanticAI + output_type structure `RoutingDecision`)
3. Fallback final : inventory

Voir `docs/routing.md` pour le detail.