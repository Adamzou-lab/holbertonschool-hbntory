from functools import wraps

from flask import abort, current_app, request
from flask_login import current_user


def role_required(role):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role != role:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def internal_token_required(view):
    """Protège les routes /api/internal/... consommées par le serveur MCP.

    Pas de session Flask-Login ici : c'est un appel machine-à-machine
    (serveur MCP -> Backoffice), authentifié par un secret partagé envoyé
    dans le header X-Internal-Token (cf. product_mcp_server/src/stock_client.py
    côté Erwan). 403 (pas 401) sur un token manquant/invalide : c'est
    exactement ce que son client attend pour le mapper en erreur claire
    côté agent.
    """

    @wraps(view)
    def wrapped(*args, **kwargs):
        expected = current_app.config["BACKOFFICE_INTERNAL_TOKEN"]
        provided = request.headers.get("X-Internal-Token")
        if not provided or provided != expected:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def same_branch_required(get_branch_id_from_request):
    """Bloque une route si la branche visée n'est pas celle du user.

    Défense en profondeur pour toute route qui recevrait un branch_id
    depuis le client (URL, form, JSON) — nos routes stock actuelles ne
    font pas ça (elles utilisent toujours current_user.branch_id), donc
    ce décorateur n'est pas branché pour l'instant, mais il est prêt si
    une route future accepte un branch_id externe.

    `get_branch_id_from_request` reçoit les mêmes *args/**kwargs que la
    vue et doit renvoyer le branch_id demandé par la requête.
    """

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            requested_branch_id = get_branch_id_from_request(*args, **kwargs)
            if current_user.branch_id != requested_branch_id:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator
