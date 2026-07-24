#!/bin/sh
# flask db upgrade et flask seed sont tous les deux idempotents (Alembic ne
# rejoue pas une migration déjà appliquée, seed vérifie qu'un admin/des
# branches existent avant d'en recréer) — donc pas de risque à les relancer
# à chaque démarrage du conteneur, même si la base existe déjà.
set -e

flask db upgrade
flask seed

exec flask run --host=0.0.0.0 --port=5000
