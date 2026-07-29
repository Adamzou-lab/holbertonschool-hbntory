# Presentation Service IA + MCP HBntory

Document de synthese pour la soutenance. Tous les choix techniques
sont justifies par les contraintes du projet (3 membres, branches
separees, integration finale).

## 1. Pourquoi un serveur MCP ?

**Model Context Protocol** (MCP) est un standard ouvert pour exposer des
outils a un LLM. Le serveur MCP HBntory agit comme une **couche de
mediation strictement controlee** entre le Service IA et les sources de
donnees reelles.

Benefices :
- Les outils sont **decouvrables** (l'agent voit leur schema JSON).
- Les outils sont **types** (Pydantic -> JSON Schema automatique).
- Les outils sont **controles** (allowlist explicite par agent).

## 2. Pourquoi un MCP maison ?

Un outil tiers comme **MCP Toolbox for Databases** donnerait au LLM un
acces SQL direct (lecture/ecriture). C'est trop large pour notre cas :
on veut des outils metier (marge brute, tendance, ranking), pas du SQL.

Le MCP maison :
- N'expose ni SQL arbitraire, ni mutation.
- Encapsule la logique metier (Decimal pour la finance, heuristique_v1
  pour la complexite, etc.).
- Permet le versionnement (methodology = "heuristic_v1").

## 3. Pourquoi read-only ?

L'agent sert un client web public, anonyme, sans authentification. Laisser
l'agent muter le stock serait equivalent a laisser n'importe qui modifier
la base. Les mutations restent dans le Backoffice, sous authentification +
controle de role + controle de branche + check quantite >= 0.

Cette separation est **defendable au jury** et **coherente avec la
specification du projet** ("ne pas faire halluciner l'agent", "ne pas
fusionner Backoffice et Service IA").

## 4. Pourquoi 4 agents ?

Avec 25 tools, un seul agent LLM a du mal a choisir lequel invoquer sans
confusion. La specialisation par domaine (4 agents) reduit l'espace des
outils visibles (allowlist stricte via `MCPToolset`) et ameliore la qualite
des reponses. Mesurable sur le jeu d'evaluation (64 questions parametrees).

| Agent | Nb tools |
|---|---|
| Inventory | 7 |
| Analytics | 10 |
| Forecast | 4 |
| Margin | 4 |
| **Total** | **25** |

## 5. Pourquoi un routeur ?

Avec 4 agents, il faut choisir lequel executer. Le routage suit 3 etapes :

1. **Mots-cles deterministes** (gratuit, rapide, explicite).
2. **LLM routeur** avec sortie structuree `RoutingDecision` (gere les cas ambigus).
3. **Fallback inventory** (defaut raisonnable).

Cas particuliers :
- `margin` sur `/query` (public) -> fallback + signalement.
- `out_of_scope` -> refus direct.

## 6. Pourquoi REST ?

- Le sujet exige "chaque question est independante, sans memoire".
- REST matche exactement ce cas d'usage (request/response, sans etat serveur).
- Pas besoin de WebSocket ni de streaming.
- FastAPI genere OpenAPI automatiquement (Swagger UI sur `/docs`).

## 7. Pourquoi sans memoire ?

- Le client web est anonyme : pas d'identifiant utilisateur a memoriser.
- Pas d'historique de conversation a proteger (RGPD).
- Cout d'inference reduit (pas de contexte conversationnel a transmettre).

## 8. Pourquoi Pydantic ?

- Validation des inputs (les LLM peuvent envoyer des champs manquants ou
  de mauvais type).
- Validation des outputs (les APIs externes peuvent renvoyer du JSON mal forme).
- Schema JSON auto-genere pour les tools MCP et les endpoints FastAPI.

## 9. Pourquoi des providers (fixture + HTTP) ?

- **Fixture** : developpement et tests sans dependance externe.
- **HTTP** : integration reelle quand une source compatible existe.
- **Interface commune** : les tools ne dependent pas de l'implementation.

Aujourd'hui, seul Forecast a un HTTP provider (Backoffice n'a pas la route).
Profitabilite reste 100% fixture (donnees synthetiques).

## 10. Pourquoi des donnees synthetiques pour Margin ?

Le projet n'inclut pas de systeme POS reel. Pas de donnees de ventes ni
d'achats dans la DB HBntory (Backoffice spec dit : stocker uniquement la
quantite de stock actuelle). Pour demontrer l'architecture sans inventer
de chiffres, on genere localement un dataset deterministe (seed + distribution
realiste) avec mention explicite `data_origin="synthetic_demo"`.

**Transparence** : les reponses de l'agent rappellent toujours que les
chiffres sont synthetiques.

## 11. Pourquoi Decimal ?

Les calculs financiers (marge brute, cout d'achat, valeur de stock)
doivent etre deterministes et reproductibles. Les `float` introduisent des
erreurs d'arrondi (ex: `0.1 + 0.2 = 0.30000000000000004`). `Decimal`
garantit une precision fixe.

## 12. Comment limiter les hallucinations ?

- **Faits uniquement via les tools.** Le system prompt l'impose, l'allowlist
  l'applique.
- **Donnees manquantes signalees explicitement.** `data_quality = low`,
  `insufficient_data`, etc.
- **Sortie structuree du routeur.** Pas de classification en texte libre.
- **Jeu d'evaluation** (64 questions) verifie qu'on ne tombe pas dans
  l'invention.
- **Pas de stack trace exposee** au LLM : juste `ToolError` avec code.

## 13. Architecture finale

```
Client web (anonyme)
        │  POST /query
        ▼
ai_service/ (FastAPI)
        │
        ├─ Router (deterministic_intent + LLM)
        │
        ├─ 4 agents PydanticAI avec allowlists
        │       │
        │       ▼
        │  product_mcp_server/ (FastMCP, Streamable HTTP)
        │       │
        │       ├─ API Produit externe (Docker)
        │       └─ API interne Backoffice (token)
        │
        └─ Endpoint interne /internal/query (X-Internal-Token)
                └─ Acces a l'agent Margin (donnees synthetiques)
```

## 14. Tests

- **127 tests** dans `ai_service/` (dont 64 evals de routage).
- **85 tests** dans `product_mcp_server/` (unitaires + contrats + integration).
- **Aucun** des tests ne requiert une cle LLM ni une API live.

## 15. Limites assumees

- Pas de source reelle pour les predictions Forecast ni la rentabilite Margin.
- Pas de streaming (REST sync).
- Pas de monitoring avance (juste `/health`).
- Couverte d'integration limitee (FastMCP en memoire, pas de serveur reel).

Voir `product_mcp_server/docs/limitations.md` pour le detail.