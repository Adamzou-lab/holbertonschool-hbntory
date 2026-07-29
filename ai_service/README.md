# HBntory AI Service

Service backend indépendant qui répond aux questions des clients (anonymes)
sur les produits et les stocks HBntory. Fait partie du **Bloc 3** (IA + client web).

> **Bloc 3 - Service IA.** Le client web est géré par Adam, ce service expose
> uniquement l'endpoint REST consommé par ce client.

## Architecture (rappel)

```
Client web (Adam)  ──HTTP POST /query──▶  Service IA (ce dossier)
                                            │
                                            ├── PydanticAI Agent (LLM)
                                            │     │
                                            │     └── MCPToolset (Streamable HTTP)
                                            │           │
                                            │           ▼
                                            │     product_mcp_server (Bloc 2)
                                            │           │
                                            │           ├── API Produit externe
                                            │           └── API interne Backoffice
```

## Endpoints

| Méthode | Path | Description |
|---|---|---|
| `POST` | `/query` | Pose une question à l'agent (réponse en texte libre + liste des outils appelés) |
| `GET` | `/health` | Probe de readiness |
| `GET` | `/tools` | Liste des outils MCP effectivement connectés (debug) |
| `GET` | `/docs` | Swagger UI auto-généré (FastAPI) |
| `GET` | `/openapi.json` | Spec OpenAPI |

### Format `POST /query`

```jsonc
// Request
{
  "question": "Dans quelle branche puis-je trouver 3 laptops 14 pouces ?"
}

// Response 200
{
  "answer": "D'après notre stock, la branche Paris a 50 unités...",
  "tool_calls": [
    {"tool": "list_branches", "args": null},
    {"tool": "get_product_availability", "args": {"product_id": "HB-LAP-1001"}}
  ]
}
```

## Choix techniques

| Décision | Valeur | Justification |
|---|---|---|
| Framework agent | **PydanticAI** | Type-safe, intégration MCP native (`MCPToolset`), output validé Pydantic |
| Framework HTTP | **FastAPI** | Async natif, OpenAPI auto, validation Pydantic des inputs |
| Provider LLM | Multi-provider (anthropic/openai/google/ollama) | Flexibilité utilisateur via env var |
| Connexion MCP | `pydantic_ai.mcp.MCPToolset` (Streamable HTTP) | Pont vers le serveur MCP HBntory |
| Mémoire | Aucune | Chaque question est stateless (conforme spec) |
| Streaming | Non | REST sync, conforme spec |
| Output | Texte libre | L'agent répond en langage naturel |

## Installation locale

```bash
cd ai_service
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env
# Editer .env : mettre votre cle API (ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.)
.venv/bin/python -m src.main
```

Le serveur écoute sur `http://localhost:8080` :

```bash
curl http://localhost:8080/health
# {"status":"ok","service":"hbntory-ai-service",...}
```

## Lancement Docker

```bash
docker build -t hbntory-ai-service ./ai_service
docker run --rm -p 8080:8080 \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  -e MCP_SERVER_URL=http://host.docker.internal:8000/mcp \
  hbntory-ai-service
```

## Variables d'environnement

| Variable | Défaut | Rôle |
|---|---|---|
| `LLM_PROVIDER` | `anthropic` | Fournisseur : `anthropic`, `openai`, `google`, `ollama`... |
| `LLM_MODEL` | `claude-3-5-sonnet-latest` | Nom du modèle chez le fournisseur |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GOOGLE_API_KEY` | – | Clé API (variable standard reconnue par PydanticAI) |
| `MCP_SERVER_URL` | `http://localhost:8000/mcp` | URL du serveur MCP (Bloc 2) |
| `AI_HOST` | `0.0.0.0` | Host d'écoute |
| `AI_PORT` | `8080` | Port d'écoute |
| `LOG_LEVEL` | `INFO` | Niveau de log |
| `REQUEST_TIMEOUT_SECONDS` | `30` | Timeout d'une requête `/query` |
| `EXPOSE_TOOLS_ENDPOINT` | `true` | Active `/tools` (debug) |

## Question types supportées (les 4 du sujet)

| Question | Outils MCP utilisés |
|---|---|
| Détail d'un produit | `get_product` (parfois `search_products` d'abord pour résoudre un nom) |
| Où est disponible un produit | `list_branches` + `get_product_availability` |
| Contenu d'une branche | `list_branches` + `get_branch_inventory` |
| Shopping list multi-produits | `get_product` (chaque item) + `check_shopping_list` |

Hors périmètre (refus explicite) : météo, politique, conseils, etc. - voir `src/prompts.py` REGLE 2.

## Garanties anti-hallucination

Le system prompt impose **5 règles** (voir `src/prompts.py`) :

1. **Faits réels uniquement** via les outils MCP - jamais d'invention.
2. **Hors périmètre** = refus explicite.
3. **Transparence** sur les produits inexistants.
4. **Langue** de la question respectée.
5. **Concision** : pas de JSON brut, réponse digérée.

## Tests

```bash
cd ai_service
.venv/bin/pytest -v
```

26 tests, aucune clé LLM ni serveur MCP réel requis :

- `tests/test_endpoints.py` (11 tests) : 200/422/503 sur `/query`, `/health`, `/tools`, OpenAPI.
- `tests/test_agent.py` (15 tests) : system prompt, build_agent, multi-provider, settings, schemas.

Les tests utilisent `FakeAgent` + `FakeMCPConnection` (voir `tests/conftest.py`).

## Tests manuels bout-en-bout

Voir [`tests/MANUAL_TESTS.md`](tests/MANUAL_TESTS.md).

## Arborescence

```
ai_service/
├── Dockerfile
├── README.md
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── .env.example
├── .dockerignore
├── .gitignore
├── src/
│   ├── __init__.py
│   ├── main.py             # FastAPI app + lifespan
│   ├── agent.py            # PydanticAI Agent
│   ├── mcp_client.py       # wrapper MCPToolset
│   ├── config.py           # pydantic-settings
│   ├── schemas.py          # requete/reponse Pydantic
│   └── prompts.py          # system prompt
└── tests/
    ├── __init__.py
    ├── conftest.py         # fixtures FakeAgent / FakeMCP
    ├── test_endpoints.py
    ├── test_agent.py
    └── MANUAL_TESTS.md
```

## Limites connues

- Nécessite un serveur MCP (Bloc 2) démarré sur `MCP_SERVER_URL` au lancement.
- Clé API LLM obligatoire au runtime (sinon `UserError` à la construction de l'agent).
- Pas de streaming : la réponse est complète en un bloc.
- Pas de mémoire : un client ne peut pas enchaîner 2 questions dans un même "fil" - chaque appel est indépendant.

## Dépendances externes

| Service | Qui le lance | Statut |
|---|---|---|
| `product_mcp_server` (Bloc 2) | Erwan (déjà livré sur `erwan`) | ✅ |
| Clé API LLM | Utilisateur (via `.env`) | ⚠️ à fournir |
| API Produit externe | Docker (fourni) | Indirect, via MCP |
| API interne Backoffice | Nico | Indirect, via MCP |
