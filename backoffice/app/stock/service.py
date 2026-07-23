"""Couche service pour les opérations de stock.

Validation faite ici (message d'erreur exploitable par les routes) en
plus de la contrainte CHECK côté base (app/models.py) : deux niveaux
de garde pour le même invariant (quantity >= 0), pas une redondance
inutile.
"""

from app.extensions import db
from app.models import Branch, Stock


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


# --- Lecture cross-branches, pour l'API interne consommée par le MCP ---
#
# Contrairement aux fonctions au-dessus (toujours bornées à une branche,
# appelées avec le branch_id du common user connecté), celles-ci n'ont
# aucune restriction de branche : c'est l'API interne (/api/internal/...,
# protégée par internal_token_required, pas par une session utilisateur)
# qui les expose au serveur MCP d'Erwan pour répondre à l'agent IA.


def stock_by_product(product_id):
    """Toutes les branches ayant une ligne de stock pour ce produit."""
    rows = (
        db.session.query(Stock, Branch)
        .join(Branch, Stock.branch_id == Branch.id)
        .filter(Stock.product_id == product_id)
        .order_by(Branch.name)
        .all()
    )
    return [
        {
            "branch_id": branch.id,
            "branch_name": branch.name,
            "quantity": stock.quantity,
        }
        for stock, branch in rows
    ]


def check_shopping_list(items):
    """Pour une liste [{product_id, quantity}], calcule quelle(s) branche(s)
    peuvent servir la commande.

    Retourne le format attendu par product_mcp_server (cf. ses tests) :
    {"branches": [...], "strategy": "single"|"split"|"unavailable",
     "recommendation": "..."}.

    - "single"      : une branche a tout ce qu'il faut -> on ne renvoie
                       qu'elle.
    - "split"       : aucune branche seule ne suffit, mais certaines ont
                       au moins un article -> on les renvoie toutes pour
                       que l'agent puisse combiner.
    - "unavailable" : aucune branche n'a le moindre article demandé.
    """
    branches = Branch.query.order_by(Branch.id).all()
    reports = []

    for branch in branches:
        item_reports = []
        missing = []
        for item in items:
            pid = item["product_id"]
            requested = item["quantity"]
            available = get_quantity(branch.id, pid)
            satisfied = available >= requested
            item_reports.append(
                {
                    "product_id": pid,
                    "requested": requested,
                    "available": available,
                    "satisfied": satisfied,
                }
            )
            if not satisfied:
                missing.append(
                    {"product_id": pid, "short": requested - available}
                )

        satisfied_count = sum(1 for i in item_reports if i["satisfied"])
        if missing:
            branch_recommendation = (
                f"{branch.name} a {satisfied_count} produit(s) sur "
                f"{len(items)}."
            )
        else:
            branch_recommendation = (
                f"{branch.name} satisfait 100% de la liste."
            )

        reports.append(
            {
                "branch_id": branch.id,
                "branch_name": branch.name,
                "items": item_reports,
                "missing": missing,
                "recommendation": branch_recommendation,
                "_satisfied_count": satisfied_count,
            }
        )

    fully_satisfying = [r for r in reports if not r["missing"]]
    if fully_satisfying:
        chosen = fully_satisfying[0]
        chosen.pop("_satisfied_count")
        return {
            "branches": [chosen],
            "strategy": "single",
            "recommendation": f"Visitez {chosen['branch_name']}.",
        }

    contributing = [r for r in reports if r["_satisfied_count"] > 0]
    for r in reports:
        r.pop("_satisfied_count")

    if contributing:
        names = ", ".join(r["branch_name"] for r in contributing)
        return {
            "branches": contributing,
            "strategy": "split",
            "recommendation": (
                f"Aucune branche ne couvre tout, combinez {names}."
            ),
        }

    return {
        "branches": [],
        "strategy": "unavailable",
        "recommendation": (
            "Aucune branche ne peut satisfaire cette liste actuellement."
        ),
    }
