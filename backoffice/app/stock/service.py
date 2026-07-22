"""Couche service pour les opérations de stock.

Validation faite ici (message d'erreur exploitable par les routes) en
plus de la contrainte CHECK côté base (app/models.py) : deux niveaux
de garde pour le même invariant (quantity >= 0), pas une redondance
inutile.
"""

from app.extensions import db
from app.models import Stock


class StockError(Exception):
    """Erreur métier stock, message affichable tel quel côté UI."""


def _get_or_create_row(branch_id, product_id):
    row = Stock.query.filter_by(
        branch_id=branch_id, product_id=product_id
    ).first()
    if row is None:
        row = Stock(branch_id=branch_id, product_id=product_id, quantity=0)
        db.session.add(row)
    return row


def add_stock(branch_id, product_id, amount):
    if amount <= 0:
        raise StockError(
            "La quantité à ajouter doit être un entier positif."
        )

    row = _get_or_create_row(branch_id, product_id)
    row.quantity += amount
    db.session.commit()
    return row


def remove_stock(branch_id, product_id, amount):
    if amount <= 0:
        raise StockError(
            "La quantité à retirer doit être un entier positif."
        )

    row = Stock.query.filter_by(
        branch_id=branch_id, product_id=product_id
    ).first()
    if row is None or row.quantity < amount:
        available = row.quantity if row else 0
        raise StockError(
            f"Stock insuffisant : {available} disponible(s), "
            f"{amount} demandé(s)."
        )

    row.quantity -= amount
    db.session.commit()
    return row


def get_branch_stock(branch_id):
    return (
        Stock.query.filter_by(branch_id=branch_id)
        .order_by(Stock.product_id)
        .all()
    )


def get_quantity(branch_id, product_id):
    row = Stock.query.filter_by(
        branch_id=branch_id, product_id=product_id
    ).first()
    return row.quantity if row else 0
