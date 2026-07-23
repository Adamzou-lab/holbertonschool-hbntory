#!/bin/sh
# Applique les migrations puis seed (idempotent, cf. app/cli.py) avant de
# démarrer le serveur, pour que le conteneur soit utilisable dès `up`.
set -e

flask db upgrade
flask seed

exec flask run --host=0.0.0.0 --port=5000
