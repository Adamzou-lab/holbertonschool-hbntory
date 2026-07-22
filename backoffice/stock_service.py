"""
Validation des opérations de stock - Pôle A.

Invariant à garantir : quantity >= 0, à chaque ajout ET retrait.

Choix : la validation est faite ici, dans une couche service, en plus de la
contrainte CHECK côté BDD (models.py). Deux niveaux de sécurité :
- ici : message d'erreur clair, utilisable par les routes Flask
- BDD : garde-fou final si jamais un bug contourne la couche service
"""

from models import db, Stock


class StockError(Exception):
    """Erreur métier stock, portant un message utilisable tel quel côté UI."""


def _get_or_create_stock_row(branch_id: int, product_id: int) -> Stock:
    row = Stock.query.filter_by(branch_id=branch_id, product_id=product_id).first()
    if row is None:
        row = Stock(branch_id=branch_id, product_id=product_id, quantity=0)
        db.session.add(row)
    return row


def add_stock(branch_id: int, product_id: int, amount: int) -> Stock:
    if amount <= 0:
        raise StockError("La quantité à ajouter doit être un entier positif.")

    row = _get_or_create_stock_row(branch_id, product_id)
    row.quantity += amount
    db.session.commit()
    return row


def remove_stock(branch_id: int, product_id: int, amount: int) -> Stock:
    if amount <= 0:
        raise StockError("La quantité à retirer doit être un entier positif.")

    row = Stock.query.filter_by(branch_id=branch_id, product_id=product_id).first()

    if row is None or row.quantity < amount:
        available = row.quantity if row else 0
        raise StockError(
            f"Stock insuffisant : {available} disponible(s), {amount} demandé(s)."
        )

    row.quantity -= amount
    db.session.commit()
    return row


def get_branch_stock(branch_id: int):
    """Liste le stock d'une branche (product_id + quantity uniquement)."""
    return Stock.query.filter_by(branch_id=branch_id).all()


def get_quantity(branch_id: int, product_id: int) -> int:
    row = Stock.query.filter_by(branch_id=branch_id, product_id=product_id).first()
    return row.quantity if row else 0
