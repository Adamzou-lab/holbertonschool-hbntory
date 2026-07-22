"""
Autorisation côté backend - Pôle A.

Règle non négociable de l'énoncé : les droits doivent être vérifiés dans la
logique serveur, jamais seulement en cachant des boutons côté template/JS.

Chaque route sensible du Backoffice doit être protégée par le decorator
adapté. Un utilisateur qui contourne l'UI (ex: appelle l'URL directement,
ou modifie le HTML) doit être bloqué ici, pas ailleurs.
"""

from functools import wraps
from flask import abort
from flask_login import current_user, login_required as flask_login_required


def login_required(view_func):
    """Alias explicite : toute route Backoffice nécessite une session active."""
    return flask_login_required(view_func)


def admin_required(view_func):
    """Réserve la route à l'unique compte admin."""

    @wraps(view_func)
    @flask_login_required
    def wrapper(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view_func(*args, **kwargs)

    return wrapper


def common_required(view_func):
    """Réserve la route aux common users (l'admin ne gère pas le stock)."""

    @wraps(view_func)
    @flask_login_required
    def wrapper(*args, **kwargs):
        if not current_user.is_common:
            abort(403)
        return view_func(*args, **kwargs)

    return wrapper


def same_branch_required(get_branch_id_from_request):
    """
    Vérifie qu'un common user n'opère que sur SA branche.

    `get_branch_id_from_request` est une fonction qui extrait le branch_id
    visé par la requête (depuis l'URL, un form, du JSON...), car cette
    logique change selon la route.

    Exemple d'utilisation :

        @app.route("/stock/<int:branch_id>/add", methods=["POST"])
        @common_required
        @same_branch_required(lambda **kw: kw["branch_id"])
        def add_stock(branch_id):
            ...
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            requested_branch_id = get_branch_id_from_request(*args, **kwargs)
            if current_user.branch_id != requested_branch_id:
                abort(403)
            return view_func(*args, **kwargs)

        return wrapper

    return decorator
