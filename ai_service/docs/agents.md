# Agents du Service IA HBntory

Le service utilise **un agent PydanticAI par domaine**, plus un agent
routeur. Chaque agent recoit uniquement les outils de son domaine (allowlist
reelle, pas juste une instruction dans le prompt).

## Pourquoi plusieurs agents ?

Avec 25 tools, un seul agent LLM a du mal a choisir lequel invoquer sans
confusion. La specialisation par domaine (4 agents) reduit l'espace des
outils visibles et ameliore la qualite des reponses (mesurable sur le jeu
d'evaluation : `tests/evals/`).

## Architecture

```
User question (POST /query ou /internal/query)
       │
       ▼
  Routage hybride (deterministic_intent puis LLM router)
       │
       ├─ Intent.INVENTORY  → inventory_agent
       ├─ Intent.ANALYTICS  → analytics_agent
       ├─ Intent.FORECAST   → forecast_agent
       ├─ Intent.MARGIN     → margin_agent         (interne uniquement)
       └─ Intent.OUT_OF_SCOPE → refus direct
```

Chaque agent est cree au demarrage (lifespan) avec :
- son system prompt specialise
- un `MCPToolset` partage filtre a ses outils uniquement

## System prompts

Voir `src/prompts.py`. Chaque prompt inclut 5 regles non negociables :

1. **Toute valeur vient d'un outil.** Jamais d'invention.
2. **Donnees manquantes = reponse explicite.** Pas de fabrication.
3. **Pas de JSON brut** dans la reponse utilisateur.
4. **Hors perimetre = refus poli.**
5. **Langue de la question respectee** (defaut francais).

Prompts specialises :
- **INVENTORY** : oriente disponibilite / quantite / branches.
- **ANALYTICS** : agregation / classements / repartitions, signale les heuristiques.
- **FORECAST** : pas de date artificielle, mentionne `data_quality` (low/medium/high).
- **MARGIN** : TOUJOURS rappelle que les donnees sont `synthetic_demo`.

## Garanties techniques

- **Allowlists reelles** : `MCPToolset` est passe avec un filtre explicite (`tools_for(intent)`).
  Un agent ne peut pas appeler un outil hors domaine, meme en forcant le prompt.
- **Aucune stack trace** dans les reponses. Le LLM recoit uniquement des messages
  `ToolError` avec codes normalises.
- **Aucun acces direct DB.** Tout passe par les tools MCP.

## Outils exposes par agent

| Agent | Outils (allowlist) |
|---|---|
| Inventory | `list_products`, `get_product`, `search_products`, `list_branches`, `get_product_availability`, `get_branch_inventory`, `check_shopping_list` |
| Analytics | `analyze_catalog_by_category`, `find_extreme_prices`, `find_extreme_weights`, `analyze_supplier_portfolio`, `estimate_catalog_stock_value`, `assess_storage_complexity`, `find_discontinued_with_stock`, `analyze_stock_distribution`, `find_overstocked_products`, `find_understocked_products` |
| Forecast | `get_stock_history`, `analyze_stock_trend`, `forecast_stockout_and_reorder`, `detect_seasonal_pattern` |
| Margin | `compute_product_margin`, `identify_most_profitable`, `compute_supplier_cost`, `analyze_storage_efficiency` |