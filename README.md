# holbertonschool-hbntory

Système de gestion de stock multi-branches : projet d'équipe Holberton (Adam, Erwan, Nico).

## Structure du projet

```
project-root/
  backoffice/           # Bloc 1 — Backoffice + base de données (Adam, Nico)
  ai_service/            # Bloc 3 — Service IA (Adam, Erwan)
  product_mcp_server/    # Bloc 2 — MCP Server + API Produit (Erwan)
  client_web/             # Bloc 3 — Client web (Adam, Erwan)
  docs/                   # Documentation partagée
  docker-compose.yml
  README.md
```

Chaque dossier correspond à un composant indépendant. Voir le `README.md` de chaque sous-dossier
pour le détail de son périmètre.

## Lancer tous les services avec Docker Compose

Préalable : l'API Produit externe (repo séparé
[hbntory-products-api](https://github.com/hbtn-edu/hbntory-products-api), fournie par l'école)
doit tourner sur `http://localhost:5001` — elle a son propre `docker compose up --build`, elle
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
(`backoffice/docker-entrypoint.sh`) — admin créé avec `ADMIN_EMAIL`/`ADMIN_PASSWORD` (voir
`.env.example`).
