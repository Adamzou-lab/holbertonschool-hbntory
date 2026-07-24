# Routage du Service IA HBntory

Le routage suit une architecture **hybride en 3 etapes** :

```
Question user
   │
   ▼
[1] deterministic_intent()        ← mots-cles
   │   match ?
   ├─── OUI ───> intent direct, confidence 0.7
   │
   └─── NON ───> [2] router_agent LLM
                     │
                     ├─── intent public (inventory/analytics/forecast)
                     │     └──> dispatch vers l'agent specialise
                     │
                     ├─── margin sur /query (public)
                     │     └──> fallback inventory + limitation signalee
                     │
                     ├─── out_of_scope
                     │     └──> refus direct
                     │
                     └─── margin sur /internal/query
                           └──> dispatch vers margin_agent
```

## Etape 1 : regles deterministes

`src/main.py::deterministic_intent` applique des regex sur la question
lowercase :

| Ordre | Pattern | Intent |
|---|---|---|
| 1 | marge, rentabilite, rentable, cout fournisseur/d'achat, freight, achat, depense, retirer | **MARGIN** |
| 2 | prevision, tendance, saisonnier, stockout, rupture, seuil, periodicite, mouvement, descendre, reapprovisionn, estim | **FORECAST** |
| 3 | top, dashboard, repartition, agreg, compar, classement, chers, lourds, surrepr, faible, fiable, categorie, discontinued, combien de, analyse | **ANALYTICS** |
| 4 | stock, disponibilit, branche, detail, produit, lyon, paris, reste-t-il, trouver, disponible | **INVENTORY** |

L'ordre est important : les mots-cles les plus specifiques sont testes en premier.
Si une question matche "marge" ET "stock", elle est classee MARGIN (le specifique
bat le generique).

## Etape 2 : agent routeur LLM

Si aucun mot-cle ne matche (cas ambigus), l'agent `router_agent` (PydanticAI)
prend le relais. Sa sortie est strictement typee :

```python
class RoutingDecision(BaseModel):
    intent: Intent  # enum
    confidence: float  # 0..1
    reason_code: str  # snake_case
```

Le system prompt force la classification dans une des 5 categories :
- `inventory` (disponibilite, branches, produits)
- `analytics` (classements, repartitions, dashboards)
- `forecast` (tendances, predictions, saisonnalite)
- `margin` (rentabilite, marges)
- `out_of_scope` (tout le reste)

## Etape 3 : dispatch + fallback

L'intent final est compare a `allowed_intents` selon l'endpoint :

- `/query` : `["inventory", "analytics", "forecast"]`
- `/internal/query` : `["inventory", "analytics", "forecast", "margin"]`

Cas particulier : si l'intent est `margin` mais l'endpoint est `/query` (public),
le service renvoie une reponse structuree :

```json
{
  "answer": "Les analyses de rentabilite sont reservees aux appels internes.",
  "intent": "margin",
  "routing_confidence": 0.95,
  "tool_calls": [],
  "data_origins": [],
  "limitations": ["margin_restricted_to_internal"],
  "request_id": "..."
}
```

Fallback final : si l'intent est `out_of_scope` ou invalide, refus direct.

## Justification du choix

- **Deterministic d'abord** : rapide, gratuit, explicite.
- **LLM en fallback** : gere les cas ambigus sans creer de faux positifs.
- **Fallback final** : pas d'inattendu cote client.

## Tests

Voir `tests/evals/test_routing_evals.py` (64 questions parametrees) :
- 15 questions Inventory
- 15 questions Analytics
- 10 questions Forecast
- 10 questions Margin
- 3 questions ambigues
- 5 questions hors perimetre
- Tests structurels (counts d'outils, non-overlap des allowlists)