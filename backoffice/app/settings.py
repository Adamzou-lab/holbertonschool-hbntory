"""Paramètres techniques éditables par l'admin (table app_settings).

Différent de app/config.py : Config vient des variables d'environnement,
fixées au démarrage du conteneur. Ici, l'admin peut changer une valeur à
chaud depuis /admin/settings sans redéployer. Quand une clé n'a jamais été
définie en base, on retombe sur le default fourni par l'appelant (qui vient
généralement de app.config).
"""

from app.extensions import db
from app.models import AppSetting

LOW_STOCK_THRESHOLD = "low_stock_threshold"
PRODUCTS_API_BASE_URL = "products_api_base_url"

SETTINGS_KEYS = (LOW_STOCK_THRESHOLD, PRODUCTS_API_BASE_URL)


def get_setting(key, default=None):
    row = db.session.get(AppSetting, key)
    if row is None or row.value is None or row.value == "":
        return default
    return row.value


def get_setting_int(key, default=None):
    raw = get_setting(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def set_setting(key, value):
    row = db.session.get(AppSetting, key)
    if row is None:
        row = AppSetting(key=key)
        db.session.add(row)
    row.value = value if value else None
    db.session.commit()
