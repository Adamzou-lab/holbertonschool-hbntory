# Decision Record — Stratégies de communication

Task 0.2. Chaque décision suit le même format : option choisie, bénéfice principal,
limite/trade-off assumé. Consigne du sujet : ne pas choisir l'option la plus complexe, choisir
celle qui correspond au besoin et à la capacité de l'équipe.

## Décision 1 — Backoffice : REST+JS ou Server-Side Rendering ?

**Choix : Server-Side Rendering (Flask + Jinja2, sans framework JS).**

- **Bénéfice principal** : une seule stack à maîtriser (Python côté serveur), pas de couche API
  interne à versionner en plus des templates, et les vérifications de rôle (`role_required`)
  restent centralisées côté backend sans risque d'incohérence avec un état client séparé.
  Adapté à une petite équipe et à un backoffice avec peu d'interactions temps réel.
- **Trade-off** : UI moins réactive qu'une SPA (rechargement de page à chaque action), et plus
  difficile à faire évoluer plus tard vers une app mobile ou un client tiers qui consommerait
  une API JSON — il faudrait alors exposer des routes REST en plus des vues SSR.

## Décision 2 — Client web ↔ Service IA : REST ou WebSocket ?

**Choix : REST.**

- **Bénéfice principal** : le sujet précise explicitement que chaque question est indépendante
  et qu'aucun historique de conversation n'est requis — c'est exactement le cas d'usage REST
  (requête → réponse, sans état à maintenir côté serveur entre deux questions). Plus simple à
  implémenter, tester et déboguer qu'un canal WebSocket, pour une équipe qui doit encore livrer
  le Backoffice, le serveur MCP et l'agent IA dans le même délai.
- **Trade-off** : pas de streaming de la réponse token par token (l'utilisateur attend la
  réponse complète), et pas de vrai temps réel si le produit évolue vers un usage plus
  conversationnel. Si le besoin de streaming devient prioritaire, WebSocket (ou SSE) sera à
  reconsidérer — mais ce n'est pas un prérequis du MVP.

## Décision 3 — Service IA ↔ Serveur MCP : quel transport ?

**Choix : MCP via Streamable HTTP (le serveur MCP Produit tourne comme un service HTTP séparé, pas en subprocess stdio).**

- **Bénéfice principal** : le serveur MCP Produit est un service à part entière dans `docker-compose.yml` (conteneur indépendant du Service IA, cf. structure suggérée du repo). Un transport HTTP permet à l'agent IA de s'y connecter comme à n'importe quel service réseau, sans dépendre du même hôte/processus — ce qui correspond à la façon dont le projet est découpé en composants Docker séparés.

- **Trade-off** : légèrement plus de configuration qu'un MCP en stdio (spawn direct du process côté agent) — il faut gérer l'URL du serveur MCP, la disponibilité réseau entre conteneurs, et potentiellement les erreurs de connexion. Le stdio aurait été plus simple mais aurait forcé à colocaliser le serveur MCP dans le même processus/conteneur que le Service IA, ce qui contredit la séparation des responsabilités demandée par le sujet.

## Décision 4 — Accès stock pour l'agent IA : MCP maison ou outil tiers ?

**Choix : étendre notre propre serveur MCP Produit avec un tool de lecture stock, plutôt qu'un outil tiers type MCP Toolbox for Databases.**

- **Bénéfice principal** : un seul serveur MCP à opérer et à sécuriser, et on garde le contrôle
  total sur ce qui est exposé à l'agent (lecture seule, pas d'accès direct SQL à la base on peut restreindre le tool à des requêtes précises, ex. "stock d'un produit par branche"). Un outil tiers générique donnerait un accès plus large à la base que nécessaire.
- **Trade-off** : plus de code à écrire/maintenir nous-mêmes (le tool stock, l'authentification éventuelle entre le MCP et le Backoffice ou la base) plutôt que de réutiliser un outil déjà
  prêt à l'emploi.

## À valider en équipe

- Le tool stock du MCP appelle-t-il une route HTTP exposée par le Backoffice, ou lit-il
  directement la base relationnelle ? (cf. note dans [architecture.md](architecture.md) §2) à trancher avec Erwan puisqu'il implémente le serveur MCP.

## Répartition

- Serveur MCP Produit (Bloc 2) : Erwan.
- Backoffice + base relationnelle (Bloc 1) : Adam, Nico.
