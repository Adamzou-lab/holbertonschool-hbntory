# holbertonschool-hbntory - Zaiko

Système de gestion de stock multi-branches : projet d'équipe Holberton (Adam, Erwan, Nico).

Deux interfaces : un **Backoffice** authentifié pour les employés/admin (gestion du stock et
des comptes), et un **Client web** public et anonyme où n'importe qui peut poser une question
en langage naturel sur les produits et le stock, traitée par un agent IA.

## Sommaire

- [Démarrage rapide](#démarrage-rapide)
- [Structure du projet](#structure-du-projet)
- [Équipe & répartition](#équipe--répartition)
- [Décisions techniques principales](#décisions-techniques-principales)
- [Fonctionnalités optionnelles implémentées](#fonctionnalités-optionnelles-implémentées)
- [Limitations connues](#limitations-connues)

## Démarrage rapide

Préalable : l'API Produit externe (repo séparé
[hbntory-products-api](https://github.com/hbtn-edu/hbntory-products-api), fournie par l'école)
doit tourner sur `http://localhost:5001` - elle a son propre `docker compose up --build`, elle
n'est pas incluse ici. Nos services y accèdent via `host.docker.internal`.

```bash
cp .env.example .env   # valeurs par défaut suffisantes pour un premier essai
docker compose up --build
```

| Service | URL |
|---|---|
| Backoffice | http://localhost:5000 |
| Client web | http://localhost:8000 |
| Service IA | http://localhost:8080 |
| Serveur MCP Produit | http://localhost:8001 |

Le Backoffice lance ses migrations et son seed automatiquement au démarrage du conteneur
(`backoffice/docker-entrypoint.sh`) - admin créé avec `ADMIN_EMAIL`/`ADMIN_PASSWORD` (voir
`.env.example`).

Guide détaillé (logs attendus étape par étape, vérifications, pièges connus, dépannage) :
[docs/docker.md](docs/docker.md).

## Structure du projet

```
project-root/
  backoffice/           # Bloc 1 - Backoffice + base de données (Adam, Nico)
  ai_service/            # Bloc 3 - Service IA (Adam, Erwan)
  product_mcp_server/    # Bloc 2 - MCP Server + API Produit (Erwan)
  client_web/             # Bloc 3 - Client web (Adam, Erwan)
  docs/                   # Documentation partagée
  docker-compose.yml
  README.md
```

Chaque dossier correspond à un composant indépendant. Voir le `README.md` de chaque sous-dossier
pour le détail de son périmètre.

## Équipe & répartition

| Membre | Périmètre principal |
|---|---|
| **Adam** | Client web, Service IA (mise en place), Backoffice (thème, dashboard admin, disponibilité cross-branches, fixes sécurité), documentation projet |
| **Nico** | Backoffice + base relationnelle (fondations : modèles, auth, stock) |
| **Erwan** | Serveur MCP Produit (Bloc 2) et Service IA (agent réel PydanticAI, architecture multi-agent, tools analytics/forecast/margin) |

Répartition détaillée dans [docs/decisions.md](docs/decisions.md) (§ Répartition).

## Décisions techniques principales

Détail complet et justifié dans [docs/decisions.md](docs/decisions.md) - résumé :

| Décision | Choix | Pourquoi (en bref) |
|---|---|---|
| Backoffice : REST+JS ou SSR ? | **Server-Side Rendering** (Flask/Jinja2) | Une seule stack à maîtriser, rôles vérifiés côté serveur sans état client séparé à synchroniser ; le sujet précise que le visuel n'est pas la priorité. |
| Client web ↔ Service IA | **REST** (pas WebSocket) | Chaque question est indépendante, aucun historique requis - exactement le cas d'usage REST, plus simple à livrer dans les délais. |
| Service IA ↔ serveur MCP | **MCP via Streamable HTTP** | Le MCP est un service à part entière (conteneur indépendant), conforme à la séparation des responsabilités demandée. |
| Accès stock pour l'agent IA | **Étendre notre propre serveur MCP** (pas d'outil tiers type MCP Toolbox) | Contrôle total sur ce qui est exposé (lecture seule), un seul serveur à sécuriser. |
| Mots de passe | `werkzeug.security` (`scrypt` en interne) | Fonction de dérivation conçue pour les mots de passe (lente, salée) - contrairement à un hash générique type SHA256, pas adapté au stockage de secrets. |
| Session Backoffice | Cookie de session (Flask-Login), pas de JWT | App web classique consommée par un navigateur, pas une API tierce à authentifier. |

## Fonctionnalités optionnelles implémentées

Au-delà du MVP strict du sujet (voir [docs/mvp.md](docs/mvp.md) pour le détail et la
justification de chacune) :

- Historique des mouvements de stock, transferts entre branches, prévisions de rupture
  (moyenne mobile simple).
- Import/export CSV du stock.
- Fiche produit détaillée + disponibilité cross-branches (informative, pas d'action).
- Paramètres admin éditables à chaud (seuil de stock faible, URL de l'API Produit).
- Dashboard admin cross-branches (lecture seule), export CSV global, journal des actions admin.
- Animations sur le chat du Client web (feedback de chargement, effet d'écriture progressive).
- Côté Service IA / MCP (Erwan) : 25 tools MCP (contre 7 initialement) répartis en 4 domaines
  (inventaire, analytics, prévisions, marge), architecture multi-agent avec routeur - voir
  `ai_service/docs/agents.md` et `product_mcp_server/docs/tools.md`.

## Limitations connues

- **Prévisions de rupture** (`stock_history`, `forecast_stockout_and_reorder`) : régression
  linéaire simple sur l'historique réel, pas un modèle prédictif - indicatif seulement, surtout
  peu fiable avec peu de données.
- **Analyses de rentabilité (marge)** : reposent sur des données **synthétiques générées**
  (aucune source de vente réelle connectée) - chaque réponse le rappelle explicitement, réservé
  à l'usage interne (`/internal/query`, jamais exposé au Client web public).
- **Un seul compte admin** : garanti par l'absence de tout formulaire de création d'un second
  admin dans l'interface, pas par une contrainte dure en base de données.
- SSL/TLS non implémenté (explicitement non requis par le sujet pour ce projet).

`docker compose up --build` a été vérifié bout-en-bout (les 4 services + l'API Produit externe,
test fonctionnel réel dans un navigateur) - voir [docs/docker.md](docs/docker.md) pour le détail
et les pièges rencontrés.
