# Lancer la stack complète avec Docker Compose

Déroulé vérifié de bout en bout : les 4 services démarrent, et une question posée
depuis le Client web remonte une réponse calculée sur les vraies données du
Backoffice et de l'API Produit externe.

## Prérequis

- Docker avec Compose v2 (`docker compose version`).
- Le repo **hbntory-products-api** cloné **à côté** de ce repo (pas dedans) :
  c'est l'API Produit externe fournie par l'école, en lecture seule. Elle n'est
  pas un service de notre `docker-compose.yml` et se lance séparément.

```bash
# depuis le dossier parent de holbertonschool-hbntory
git clone https://github.com/hbtn-edu/hbntory-products-api.git
```

Arborescence attendue :

```
un-dossier-parent/
  holbertonschool-hbntory/     <- ce repo
  hbntory-products-api/        <- API Produit externe (repo école)
```

## Étape 1 - Lancer l'API Produit externe (port 5001)

Elle doit tourner **avant** le reste : le serveur MCP l'interroge dès ses
premiers appels d'outils.

```bash
cd ../hbntory-products-api
docker compose up -d
curl http://localhost:5001/health
```

Réponse attendue :

```json
{ "status": "ok", "products": 40, "suppliers": 5 }
```

Le conteneur écoute sur 5000 en interne, publié sur **5001** côté hôte - c'est
la valeur attendue par `PRODUCTS_API_BASE_URL` dans notre compose.

## Étape 2 - Configurer le `.env`

```bash
cd ../holbertonschool-hbntory
cp .env.example .env
```

Les valeurs par défaut conviennent, **sauf deux** à renseigner :

```dotenv
# Clé du provider LLM choisi (LLM_PROVIDER=anthropic par défaut)
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Protège /internal/query (analyses de marge, jamais exposées au Client web
# public). Laissé vide, l'endpoint reste fermé (503) - c'est le comportement
# par défaut voulu. À définir seulement pour démontrer la marge.
AI_INTERNAL_TOKEN=une-valeur-aleatoire-de-votre-choix
```

`.env` est dans le `.gitignore` : ne jamais y committer de vraie clé.

## Étape 3 - Vérifier que les ports sont libres

La stack publie **5000** (backoffice), **8000** (client web), **8001** (MCP) et
**8080** (service IA), en plus du **5001** de l'API Produit.

```bash
for p in 5000 5001 8000 8001 8080; do
  echo "--- $p"; lsof -nP -iTCP:$p -sTCP:LISTEN || echo "  libre"
done
```

Si un port est déjà pris, Docker échoue au démarrage avec
`ports are not available: ... bind: address already in use`. Deux issues :
libérer le processus qui l'occupe, ou remapper le port hôte dans un
`docker-compose.override.yml` local (voir « Surcharges locales » plus bas).

> Attention si vous remappez un port dans un override : Compose **concatène**
> les listes `ports` au lieu de les remplacer. Sans le tag `!override`, le
> mapping du fichier de base reste actif et le conflit persiste.
>
> ```yaml
> services:
>   backoffice:
>     ports: !override
>       - "5010:5000"
> ```

## Étape 4 - Lancer la stack

```bash
docker compose up --build
```

Sans `-d`, pour voir les logs des 4 services. Le premier build prend quelques
minutes (4 images).

## Étape 5 - Ordre de démarrage attendu

L'ordre n'est pas cosmétique, il est contraint dans le compose :

1. **backoffice** - applique ses migrations Alembic puis son seed
   automatiquement (`backoffice/docker-entrypoint.sh`), avant de lancer
   gunicorn. Au premier démarrage on voit défiler les `Running upgrade ...`,
   puis la création de l'admin ; aux suivants, `Un admin existe déjà, rien à
   faire.` (la base vit dans le volume nommé `backoffice_db`).
2. **mcp** - `depends_on: backoffice`, plus un `healthcheck` sur `/health`.
3. **ai_service** - `depends_on: mcp` avec `condition: service_healthy`. Cette
   condition est indispensable : `MCPConnection.connect()` est appelé dans le
   lifespan FastAPI sans `try/except`, donc le service **plante** si le MCP ne
   répond pas encore. `depends_on` seul ne garantirait que l'ordre de
   lancement, pas que `/health` réponde.
4. **client_web** - nginx, indépendant, démarre quand il veut.

Signe que la chaîne est bien montée, dans les logs de `ai_service` :

```
INFO src.mcp_client: Connecting to MCP server at http://mcp:8000/mcp
INFO mcp.client.streamable_http: Negotiated protocol version: 2025-11-25
INFO src.mcp_client: MCP server connected
INFO src.main: HBntory AI Service ready on 0.0.0.0:8080 (provider=anthropic, model=...)
```

Vérification de l'état réel des conteneurs :

```bash
docker compose ps
# mcp doit afficher (healthy)
```

## Étape 6 - Vérifier chaque service

```bash
# 1. API Produit externe
curl http://localhost:5001/health
# {"status":"ok","products":40,"suppliers":5}

# 2. Backoffice - 302 vers /login (normal, tout est authentifié)
curl -o /dev/null -w "%{http_code} -> %{redirect_url}\n" http://localhost:5000/

# 3. Serveur MCP
curl http://localhost:8001/health
# {"status":"ok","service":"hbntory-product-mcp"}

# 4. Service IA
curl http://localhost:8080/health
# {"status":"ok","service":"hbntory-ai-service","mcp_server_url":"http://mcp:8000/mcp",...}

# Les 25 outils MCP vus à travers le Service IA
curl -s http://localhost:8080/tools

# 5. Client web
curl -o /dev/null -w "%{http_code}\n" http://localhost:8000/
```

Le champ `mcp_server_url` du `/health` du Service IA doit valoir
`http://mcp:8000/mcp` (nom de service Docker). Toute autre valeur signifie que
vous n'interrogez pas le service du compose (voir « Pièges connus »).

L'endpoint interne, protégé par `AI_INTERNAL_TOKEN` :

```bash
# sans token -> 401
curl -X POST http://localhost:8080/internal/query \
  -H 'Content-Type: application/json' -d '{"question":"test"}'

# avec token -> 200, intent "margin", data_origins ["synthetic_demo"]
curl -X POST http://localhost:8080/internal/query \
  -H 'Content-Type: application/json' \
  -H "X-Internal-Token: $AI_INTERNAL_TOKEN" \
  -d '{"question":"Quels sont les produits les plus rentables ?"}'
```

## Étape 7 - Test bout-en-bout

Ouvrir <http://localhost:8000> et poser une question, par exemple :

> Quels produits sont disponibles à la Branche Lyon ?

Le seed crée 3 branches (Lyon, Paris, Marseille) et 9 lignes de stock, donc la
réponse est vérifiable. Pour Lyon :

| Produit | Référence | Quantité |
|---|---|---|
| Holberton Student Laptop 14 | HB-LAP-1001 | 12 |
| Mechanical Keyboard EN | HB-KBD-4101 | 30 |
| Wireless Mouse | HB-MSE-4201 | 25 |

Vérifier que les chiffres affichés correspondent : c'est ce qui distingue une
vraie réponse d'une réponse plausible mais fabriquée. Comparer avec la source :

```bash
docker compose exec backoffice python -c "
import sqlite3
c = sqlite3.connect('/data/backoffice.db')
print(c.execute('select branch_id, product_id, quantity from stocks where branch_id=1').fetchall())
"
```

Et confirmer côté logs que la requête a bien traversé la stack :

```bash
docker compose logs client_web | grep "POST /query"   # relai nginx
docker compose logs ai_service | grep "POST /query"   # service IA atteint
docker compose logs mcp        | grep "POST /mcp"     # outils appelés
```

Une chaîne complète produit, dans les logs d'`ai_service`, une alternance
d'appels `api.anthropic.com/v1/messages` et `mcp:8000/mcp` : l'agent raisonne,
appelle un outil, re-raisonne.

## Pièges connus

### 1. Le serveur MCP crashe au démarrage : `No module named 'mcp.server.fastmcp'`

Symptôme - `mcp` sort en code 1 immédiatement, et `ai_service` refuse alors de
démarrer (`dependency failed to start`) :

```
ModuleNotFoundError: No module named 'mcp.server.fastmcp'
```

Cause - le SDK Python `mcp` **2.0** a supprimé le module
`mcp.server.fastmcp` (`FastMCP` y est renommé `MCPServer`). Or tout
`product_mcp_server/src/` est écrit contre l'API FastMCP 1.x (`server.py`,
`errors.py`, `tools/*`). La contrainte d'origine `mcp[cli]>=1.2` étant sans
borne haute, un build fait aujourd'hui installe la 2.x et casse.

Correctif - la borne est désormais dans `product_mcp_server/requirements.txt` :

```
mcp[cli]>=1.2,<2
```

Si le crash réapparaît, vérifier la version réellement installée dans l'image :

```bash
docker compose exec mcp pip show mcp   # doit être une 1.x
```

Note : `ai_service` n'est pas concerné, `pydantic-ai` borne déjà `mcp` en 1.x.

### 2. Le navigateur reçoit une réponse d'un autre Service IA que le vôtre

Symptôme - le pire des pièges, parce qu'il ne produit **aucune erreur** : le
chat répond normalement, mais avec des données qui ne correspondent pas à la
base (mauvais nombre de produits, quantités fantaisistes). Et les logs montrent
que le Service IA du compose n'a jamais reçu la requête :

```bash
docker compose logs ai_service | grep -c "POST /query"   # 0 alors qu'on vient de poser une question
```

Cause - le front appelait auparavant `http://127.0.0.1:8080/query`, une URL
d'hôte codée en dur. Or sur un poste de dev, un port-forward (VS Code Remote /
tunnel, devcontainer, ancien service laissé tourner) peut déjà écouter sur
`127.0.0.1:8080` et intercepter l'appel, le relayant vers un **autre** Service
IA, branché sur un autre MCP et d'autres données. À noter que `localhost` ne
protège pas : il peut se résoudre en `127.0.0.1` comme en `::1` selon
l'OS et le navigateur, donc retomber sur l'intercepteur.

Diagnostic - comparer les deux résolutions ; si elles diffèrent, il y a un
intercepteur :

```bash
curl -s http://localhost:8080/health
curl -s http://127.0.0.1:8080/health
lsof -nP -iTCP:8080 -sTCP:LISTEN
```

Correctif - l'appel est maintenant **same-origin** : `client_web/static/js/app.js`
utilise l'URL relative `/query`, et nginx (`client_web/nginx.conf`) la relaie
vers `ai_service:8080` par le réseau interne de Compose. Plus d'hôte codé en
dur, plus de dépendance au CORS, et plus d'interception possible. Le proxy
résout `ai_service` via le DNS Docker (`resolver 127.0.0.11`) à chaque requête,
pour que nginx démarre même si le Service IA n'est pas encore prêt, et pose un
`proxy_read_timeout` large (un appel agent enchaîne plusieurs allers-retours
LLM et dépasse le défaut de 60 s).

Corollaire : ne pas réintroduire d'URL absolue côté front.

### 3. `host.docker.internal` sur Linux

Le backoffice et le MCP joignent l'API Produit externe via
`http://host.docker.internal:5001`, car elle tourne sur l'hôte et non dans
notre réseau Compose. Ce nom est fourni nativement par Docker Desktop
(macOS/Windows) mais **pas** par Docker Engine sur Linux natif - d'où le
`extra_hosts` déjà présent dans `docker-compose.yml` pour les deux services :

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

Si un outil produit remonte une erreur de connexion sur Linux, vérifier que ce
bloc est bien là, et que l'API Produit écoute sur `0.0.0.0` et non `127.0.0.1`.

## Surcharges locales

Un conflit de port ou un réglage propre à votre poste se met dans un
`docker-compose.override.yml` à la racine : Compose le charge automatiquement,
et il est `.gitignore` - donc jamais imposé au reste de l'équipe. Ne pas
modifier `docker-compose.yml` pour un besoin individuel.

## Lancer les tests

Aucun venv n'est nécessaire, les images contiennent déjà les dépendances
runtime ; seul `pytest` s'ajoute.

```bash
docker run --rm -v "$PWD/product_mcp_server:/app" -w /app \
  holbertonschool-hbntory-mcp \
  sh -c "pip install -q -r requirements-dev.txt && python -m pytest -q"

docker run --rm -v "$PWD/ai_service:/app" -w /app \
  holbertonschool-hbntory-ai_service \
  sh -c "pip install -q -r requirements-dev.txt && python -m pytest -q"

# --entrypoint sh est obligatoire ici : l'image backoffice a un ENTRYPOINT qui
# lance migrations + gunicorn et ignorerait la commande (le conteneur
# semblerait « bloqué » alors qu'il sert simplement le site).
docker run --rm --entrypoint sh -v "$PWD/backoffice:/app" -w /app \
  holbertonschool-hbntory-backoffice \
  -c "pip install -q -r requirements-dev.txt && python -m pytest -q"
```

## Arrêt et remise à zéro

```bash
docker compose down            # arrête, conserve la base (volume backoffice_db)
docker compose down -v         # supprime aussi la base -> migrations + seed rejoués
docker compose logs -f         # suivre les logs si lancé avec -d
docker compose up --build -d   # relancer en arrière-plan
```

Ne pas oublier l'API Produit externe, qui a son propre cycle de vie :

```bash
cd ../hbntory-products-api && docker compose down
```
