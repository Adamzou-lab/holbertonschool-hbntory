#!/bin/sh
# flask db upgrade et flask seed sont tous les deux idempotents (Alembic ne
# rejoue pas une migration déjà appliquée, seed vérifie qu'un admin/des
# branches existent avant d'en recréer) — donc pas de risque à les relancer
# à chaque démarrage du conteneur, même si la base existe déjà.
set -e

flask db upgrade
flask seed

# gunicorn plutôt que `flask run` : ce dernier est le serveur de dev de
# Flask, mono-thread et explicitement déconseillé en dehors du dev local.
# -w 1 (un seul worker) volontaire : la base SQLite est un fichier unique,
# plusieurs workers en écriture concurrente dessus risquent des erreurs
# "database is locked" ; --threads 4 garde de la concurrence pour les
# appels I/O (résolution produit vers l'API externe) sans ce risque.
exec gunicorn -w 1 --threads 4 -b 0.0.0.0:5000 wsgi:app
