# Service IA — StockFlow (MOCK actuel)

**Ce service est actuellement un mock.** Il expose le contrat REST attendu par le Client Web,
avec des réponses à base de mots-clés (pas de vrai agent, pas de connexion au serveur MCP).
Erwan branchera le vrai agent (Task 4-5, `docs/decisions.md`) sur ce même contrat.

## Contrat REST

- `GET /health` → `{"status": "ok", "mode": "mock"}`
- `POST /api/query` avec `{"question": "..."}` → `{"answer": "..."}` (200), ou
  `{"error": "..."}` (400) si `question` est vide/absente.

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
