# Service IA — StockFlow (MOCK actuel)

**Ce service est actuellement un mock.** Il expose le contrat REST attendu par le Client Web,
avec des réponses à base de mots-clés (pas de vrai agent, pas de connexion au serveur MCP).
Erwan branchera le vrai agent (Task 4-5, `docs/decisions.md`) sur ce même contrat.

## Contrat REST

- `GET /health` → `{"status": "ok", "mode": "mock"}`
- `POST /api/query` avec `{"question": "..."}` → `{"answer": "..."}` (200), ou
  `{"error": "..."}` (400) si `question` est vide/absente.

## Types de questions supportées (Task 5.1)

4 catégories, reprises directement du sujet et alignées sur les 4 tools stock du serveur MCP
d'Erwan (`product_mcp_server/src/tools/stock_tools.py`) — quand le vrai agent remplacera le mock,
chaque catégorie appellera le tool du même nom :

| Catégorie | Exemple de question | Tool MCP qui répondra (à terme) |
|---|---|---|
| `product_details` | « Donne-moi les détails du produit HB-MON-2101. » | `get_product` |
| `product_availability` | « Où trouver le produit HB-LAP-1001 ? » | `get_product_availability` |
| `branch_inventory` | « Quels produits sont disponibles à la Branche Lyon ? » | `get_branch_inventory` |
| `shopping_list` | « Si je veux 3 HB-LAP-1001 et 2 HB-MON-2101, quelle branche visiter ? » | `check_shopping_list` |

**Hors périmètre** : toute question qui ne rentre dans aucune de ces 4 catégories reçoit un
message explicite disant que ce n'est pas supporté, plutôt qu'une réponse inventée (exigence du
sujet Task 5 : "the response should clearly state that the information is unavailable").

La fonction `classify()` dans `app.py` fait ce classement (mots-clés simples pour l'instant côté
mock). C'est cette même fonction qui devra, à terme, décider quel(s) tool(s) MCP appeler pour
composer la réponse réelle.

## Lancer en local

```bash
cd ai_service
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py   # écoute sur http://127.0.0.1:5002
```

## Pourquoi Flask-Cors ici et pas côté Backoffice ?

Le Backoffice sert ses propres pages (SSR), donc pas de requête cross-origin. Le Client Web,
lui, est une page statique servie séparément (autre port/domaine) qui appelle ce service en
`fetch()` — sans CORS activé, le navigateur bloquerait la requête par la politique same-origin.
