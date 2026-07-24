"""Journalisation des actions d'admin sur les comptes (app/models.py::
AdminAction) — un seul point d'écriture pour rester cohérent, comme
app/stock/service.py::_log_movement pour les mouvements de stock."""

from app.extensions import db
from app.models import AdminAction


def log_admin_action(actor_id, target_user_id, action_type):
    db.session.add(
        AdminAction(
            actor_id=actor_id,
            target_user_id=target_user_id,
            action_type=action_type,
        )
    )
