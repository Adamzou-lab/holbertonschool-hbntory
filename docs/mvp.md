# MVP — Définition

Task 0.3. Le MVP couvre tout le périmètre obligatoire du sujet, sans extra. Découpage en trois
niveaux : à faire en premier, à faire ensuite, optionnel si le temps le permet.

## Priorité 1 — à implémenter en premier (bloquant pour le reste)

Le reste du système (MCP, IA, client web) dépend des données de stock — donc le Backoffice et la
base doivent exister avant tout le reste.

- Modèle de données : `Branch`, `User`, `Stock` (SQLAlchemy + migrations Flask-Migrate).
- Auth Backoffice : login/logout, session (Flask-Login), hash des mots de passe
  (`werkzeug.security`), un seul compte admin.
- Décorateur `role_required` et vérification des rôles côté backend (jamais seulement côté
  template).
- Admin : lister les users, créer un common user, assigner une branche, soft-delete, modifier,
  changer mot de passe, changer branche. Aucune gestion de stock côté admin.
- Common user : rattaché à une seule branche. Ajouter/retirer/consulter le stock de sa branche
  uniquement. Validation : quantité jamais négative, refuser si l'opération ferait passer le
  stock en négatif.
- Common user : lister les produits en stock pour sa branche (id produit uniquement à ce stade,
  pas encore le nom — dépend de l'intégration API Produit, priorité 2).

## Priorité 2 — ensuite

- Intégration Backoffice → API Produit externe (Docker) : résoudre les `product_id` en
  nom/description pour l'affichage de la liste de stock côté common user.
- Serveur MCP Produit : tools `list_products`, `get_product` (bridge vers l'API Produit).
- Tool stock côté serveur MCP (lecture seule) — implémentation de la Décision 4
  ([decisions.md](decisions.md)).
- Service IA : squelette du service indépendant, connexion au serveur MCP (Décision 3), premier
  agent capable de répondre à une question simple type "quel produit correspond à cet id ?"
  en s'appuyant uniquement sur les tools (pas d'invention de réponse).
- Client web : page simple (REST, Décision 2) qui envoie une question au Service IA et affiche
  la réponse.

## Priorité 3 — optionnel si le temps le permet

- Questions multi-produits complexes ("si je veux 3 X, 2 Y et 4 Z, quelle(s) branche(s)
  visiter ?") nécessitant que l'agent croise plusieurs appels de tools et agrège le résultat.
- Amélioration du style visuel du Backoffice et du client web (le sujet précise que le visuel
  n'est pas la priorité).
- Recherche/filtre sur la liste de produits en stock.
- Passage du Client web de REST vers WebSocket/streaming si le besoin de temps réel se confirme.
- Docker Compose orchestrant l'ensemble des services (Backoffice, MCP, Service IA, Client web,
  API Produit) en une seule commande.

## Mise à jour — fonctionnalités réintégrées (2026-07-23)

Ces fonctionnalités avaient été coupées de la maquette exploratoire initiale
(`docs/mockups/stock-dashboard.html`) pour rester strictement dans le MVP du
sujet. Décision d'équipe (Adam) : les réintégrer, une fois le MVP strict
posé et fonctionnel. Toutes lisent/écrivent uniquement des données déjà
locales (stock, mouvements) ou interrogent l'API Produit en direct sans
rien stocker — aucune ne viole la règle d'or (§ci-dessous).

- **Historique des mouvements de stock** (`StockMovement`) : chaque
  add/remove/transfert est journalisé (produit, quantité, branche, auteur,
  date). Écran dédié pour le common user (`/stock/history`).
- **Transferts de stock entre branches** : opération atomique (les deux
  branches sont mises à jour dans le même commit, ou aucune), journalisée
  comme deux mouvements liés (`transfer_out`/`transfer_in`).
- **Prévisions de rupture de stock** : estimation basée sur la moyenne des
  sorties réelles (retraits + transferts sortants) des 30 derniers jours.
  Renvoie "pas assez de données" plutôt qu'un chiffre inventé s'il n'y a pas
  d'historique — même principe que les réponses de l'agent IA (jamais
  d'invention sans données pour l'étayer).
- **Import/export CSV** du stock d'une branche (colonnes `product_id`,
  `quantity`). L'import se comporte comme un ajout (`add_stock`), jamais un
  écrasement destructif.
- **Fiche produit détaillée + image** : résolue en direct depuis l'API
  Produit externe à l'affichage (même client que la liste de stock,
  `app/products/client.py`) — toujours rien de stocké localement.
- **Paramètres admin (config technique)** : seuil de stock faible et
  surcharge de l'URL de l'API Produit, éditables à chaud sans redéploiement
  (table `app_settings`).
- **Dashboard admin** (2026-07-24) : vue d'ensemble cross-branches en
  lecture seule (`/admin/dashboard`, nouvel écran d'accueil de l'admin) —
  nombre de produits référencés et quantité totale par branche, plus la
  liste des lignes sous le seuil de stock faible toutes branches
  confondues. Comble un vide réel (l'admin n'avait jusque-là aucune
  visibilité sur le stock, seulement la gestion des users) sans violer
  "aucune gestion de stock côté admin" : uniquement de la lecture, aucune
  action de modification sur cet écran.

## Hors scope (explicitement exclu par le sujet)

- SSL/TLS (non requis pour ce projet).
- Historique de conversation côté client web.
- Création de plusieurs comptes admin.
- Stockage de toute donnée produit (nom, prix, description, image) en base locale.
