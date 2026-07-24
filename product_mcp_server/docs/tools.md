# Catalogue des 25 tools MCP HBntory (Bloc 2)

## Architecture

```
25 tools = 3 produit + 4 stock + 10 analytics + 4 forecast + 4 margin

Chaque tool est read-only.
Les donnees de rentabilite (margin) sont synthetiques (data_origin=synthetic_demo).
```

## Produit (3)

| Tool | Input | Output | Source |
|---|---|---|---|
| `list_products` | `category?`, `supplier_id?`, `include_discontinued?=False`, `limit?=20`, `offset?=0` | `{products: [...], total: int, limit, offset}` | API Produit externe |
| `get_product` | `product_id: str` (SKU ou numerique) | Objet `Produit` | API Produit externe |
| `search_products` | `query: str`, `limit?=10` | `{products: [...]}` | API Produit externe |

## Stock (4)

| Tool | Input | Output | Source |
|---|---|---|---|
| `list_branches` | – | `{branches: [{id, name}]}` | API interne Backoffice |
| `get_product_availability` | `product_id: str` | `{product_id, branches: [{branch_id, branch_name, quantity}], total}` | API interne Backoffice |
| `get_branch_inventory` | `branch_id: int` | `{branch_id, items: [...], total_items}` | API interne Backoffice |
| `check_shopping_list` | `items: list[{product_id, quantity}]` | `{strategy, branches: [...], recommendation}` | API interne Backoffice |

## Analytics (10) — Phase 1

| Tool | Input | Output |
|---|---|---|
| `analyze_catalog_by_category` | – | `{categories: [{category, product_count, avg_price, min_price, max_price, total_weight_kg, missing_price_count, missing_weight_count, currencies}], products_analyzed}` |
| `find_extreme_prices` | `direction: "highest"\|"lowest"`, `limit: 1..20=5`, `category?` | `{direction, limit, category, products}` |
| `find_extreme_weights` | `direction: "heaviest"\|"lightest"`, `limit: 1..20=5` | `{direction, limit, products, missing_weight_count}` |
| `analyze_supplier_portfolio` | – | `{suppliers: [{supplier_id, supplier_name, country, lead_time_days, reliability_score, product_count, categories_covered, avg_price}], suppliers_with_full_metadata}` |
| `estimate_catalog_stock_value` | – | `{total_value, currency, missing_price_count, warning, by_category, by_branch}` |
| `assess_storage_complexity` | `limit: 1..100=20` | `{methodology: "heuristic_v1", products: [{sku, name, weight_kg, category, complexity_score, factors}]}` |
| `find_discontinued_with_stock` | – | `{products: [{sku, name, category, total_stock, branches, review_required}]}` |
| `analyze_stock_distribution` | – | `{by_branch: [...], concentration: {gini_index, top_branch_share, method}}` |
| `find_overstocked_products` | `threshold_units: int=50`, `limit: 1..50=10` | `{threshold_units, method, products}` |
| `find_understocked_products` | `threshold_units: int=5`, `limit: 1..50=10`, `category?` | `{threshold_units, category, method, products}` |

## Forecast (4) — Phase 2 (donnees fixture)

| Tool | Input | Output |
|---|---|---|
| `get_stock_history` | `product_id: str`, `days: 3..365=30`, `branch_id?` | `{product_id, days, calculation_basis, history}` |
| `analyze_stock_trend` | `product_id: str`, `days: 7..365=90` | `{product_id, days, global: {direction, avg_daily_change, r_squared, moving_average_7d, data_quality}, by_branch, calculation_basis}` |
| `forecast_stockout_and_reorder` | `product_id: str`, `branch_id: int`, `safety_buffer_days: 0..60=7`, `days: 7..365=90` | `{product_id, branch_id, current_quantity, avg_daily_movement?, safety_buffer_days, estimated_stockout_date?, recommended_reorder_date?, hypotheses, limitations, data_quality}` |
| `detect_seasonal_pattern` | `product_id: str`, `days: 90..730=365` | `{product_id, has_pattern, best_period_days?, autocorrelation_at_best_lag?, cycles_completed, peak_months, low_months, data_quality, candidate_periods_days, calculation_basis, limitations}` |

**Valeurs `None`** quand le calcul est impossible (qualite insuffisante, mouvement nul).
**`data_quality`** = low / medium / high — pas de "confidence" (terme reserve aux statistiques).

## Margin (4) — Phase 3 (donnees synthetiques)

| Tool | Input | Output |
|---|---|---|
| `compute_product_margin` | `product_id: str`, `days: 1..365=90` | `{product_id, product_name?, period_days, units_sold, gross_revenue, weighted_avg_unit_cost, cost_of_goods_sold, gross_margin, gross_margin_rate?, return_on_cost?, currency, has_purchase_data, has_sales_data, data_origin: "synthetic_demo"}` |
| `identify_most_profitable` | `days: 1..365=30`, `limit: 1..50=10`, `metric: "gross_margin"\|"gross_margin_rate"\|"sales_volume"\|"return_on_cost"=gross_margin` | `{metric, days, limit, products: [...], data_origin}` |
| `compute_supplier_cost` | `days: 1..365=90` | `{days, suppliers: [{supplier_id, supplier_name?, total_purchase_cost, total_freight_cost, total_cost, order_count, avg_lead_time_days?, on_time_pct?, currency}], data_origin}` |
| `analyze_storage_efficiency` | `days: 1..365=90` | `{days, products: [{product_id, product_name?, complexity_score?, total_margin, units_sold, margin_per_complexity?, recommendation: "keep"\|"review"\|"reduce"\|"drop_candidate", rationale}], data_origin, warning}` |

**`data_origin: "synthetic_demo"`** dans chaque reponse.
**`recommendation`** = suggestion heuristique NON automatique (validation humaine recommandee).
**`Decimal`** pour tous les calculs monetaires.

## Garanties communes

- Tous les outils sont **read-only** : aucune mutation (add/remove/modify stock).
- Pas d'acces SQL direct : tout passe par clients HTTP ou providers fixtures.
- Stack traces jamais exposees au LLM (ToolError avec code normalise).
- Codes d'erreur normalises : `invalid_input`, `not_found`, `upstream_timeout`,
  `upstream_unavailable`, `invalid_upstream_response`, `insufficient_data`,
  `unauthorized`, `internal_error`.