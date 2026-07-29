"""Couche service pour les opérations de stock.

Validation faite ici (message d'erreur exploitable par les routes) en
plus de la contrainte CHECK côté base (app/models.py) : deux niveaux
de garde pour le même invariant (quantity >= 0), pas une redondance
inutile.
"""

from datetime import timedelta

from app.extensions import db
from app.models import (
    MOVEMENT_ADD,
    MOVEMENT_REMOVE,
    MOVEMENT_TRANSFER_IN,
    MOVEMENT_TRANSFER_OUT,
    Branch,
    Stock,
    StockMovement,
    _utcnow,
)
from app.products.client import product_exists


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


def _log_movement(
    branch_id, product_id, movement_type, quantity, user_id,
    related_branch_id=None,
):
    db.session.add(
        StockMovement(
            branch_id=branch_id,
            product_id=product_id,
            movement_type=movement_type,
            quantity=quantity,
            related_branch_id=related_branch_id,
            user_id=user_id,
        )
    )


def add_stock(branch_id, product_id, amount, user_id):
    if amount <= 0:
        raise StockError(
            "La quantité à ajouter doit être un entier positif."
        )

    # Sujet : "Stock operations reference product identifiers that exist in
    # the external Product API, when applicable". On refuse seulement si
    # l'API a répondu clairement "non" (product_exists() -> False) ; si
    # elle est injoignable (-> None), on n'affirme rien et on laisse passer
    # plutôt que de bloquer une opération de stock critique à cause d'une
    # dépendance externe en panne — même philosophie de résilience que le
    # reste de app/products/client.py.
    if product_exists(product_id) is False:
        raise StockError(
            f"Le produit #{product_id} n'existe pas dans le catalogue."
        )

    row = _get_or_create_row(branch_id, product_id)
    row.quantity += amount
    _log_movement(branch_id, product_id, MOVEMENT_ADD, amount, user_id)
    db.session.commit()
    return row


def remove_stock(branch_id, product_id, amount, user_id):
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
    _log_movement(branch_id, product_id, MOVEMENT_REMOVE, amount, user_id)
    db.session.commit()
    return row


def transfer_stock(
    source_branch_id, target_branch_id, product_id, amount, user_id
):
    """Déplace `amount` unités de product_id de source vers target.

    Opération atomique (un seul commit) : soit les deux branches sont mises
    à jour et les deux mouvements journalisés, soit rien ne l'est.
    """
    if amount <= 0:
        raise StockError(
            "La quantité à transférer doit être un entier positif."
        )
    if source_branch_id == target_branch_id:
        raise StockError("La branche de destination doit être différente.")
    if db.session.get(Branch, target_branch_id) is None:
        raise StockError("Branche de destination introuvable.")

    source_row = Stock.query.filter_by(
        branch_id=source_branch_id, product_id=product_id
    ).first()
    if source_row is None or source_row.quantity < amount:
        available = source_row.quantity if source_row else 0
        raise StockError(
            f"Stock insuffisant pour transférer : {available} "
            f"disponible(s), {amount} demandé(s)."
        )

    target_row = _get_or_create_row(target_branch_id, product_id)
    source_row.quantity -= amount
    target_row.quantity += amount

    _log_movement(
        source_branch_id, product_id, MOVEMENT_TRANSFER_OUT, amount,
        user_id, related_branch_id=target_branch_id,
    )
    _log_movement(
        target_branch_id, product_id, MOVEMENT_TRANSFER_IN, amount,
        user_id, related_branch_id=source_branch_id,
    )
    db.session.commit()
    return source_row


def get_branch_history(branch_id, limit=50):
    return (
        StockMovement.query.filter_by(branch_id=branch_id)
        .order_by(StockMovement.created_at.desc())
        .limit(limit)
        .all()
    )


def estimate_days_left(
    branch_id, product_id, current_quantity, window_days=30
):
    """Estimation grossière (moyenne mobile) du nombre de jours avant
    rupture, basée sur les sorties réelles (remove + transfer_out) des
    `window_days` derniers jours.

    Retourne None si on n'a pas assez de données pour estimer plutôt que
    d'inventer un chiffre — même logique que l'agent IA côté MCP : pas de
    réponse fabriquée sans données pour l'étayer.
    """
    since = _utcnow() - timedelta(days=window_days)
    outflow = (
        db.session.query(db.func.sum(StockMovement.quantity))
        .filter(
            StockMovement.branch_id == branch_id,
            StockMovement.product_id == product_id,
            StockMovement.movement_type.in_(
                [MOVEMENT_REMOVE, MOVEMENT_TRANSFER_OUT]
            ),
            StockMovement.created_at >= since,
        )
        .scalar()
    )
    if not outflow:
        return None

    daily_rate = outflow / window_days
    if daily_rate <= 0:
        return None
    return round(current_quantity / daily_rate, 1)


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


def get_all_stock():
    """Toutes les lignes de stock, toutes branches confondues, triées par
    branche puis produit — pour l'export CSV global de l'admin (lecture
    seule, cf. dashboard_overview ci-dessous)."""
    return (
        db.session.query(Stock, Branch)
        .join(Branch, Stock.branch_id == Branch.id)
        .order_by(Branch.name, Stock.product_id)
        .all()
    )


def dashboard_overview(low_stock_threshold):
    """Vue d'ensemble en lecture seule pour l'admin (ajouté hors MVP
    initial) : jamais de modification depuis cet écran, cf. mvp.md
    "Aucune gestion de stock côté admin" — uniquement de la visibilité
    cross-branches, ce que l'admin n'a actuellement aucun moyen de voir.

    Retourne (par_branche, alertes_stock_faible) :
    - par_branche : une entrée par Branch, avec nombre de lignes de stock,
      quantité totale et nombre de lignes sous le seuil.
    - alertes_stock_faible : toutes les lignes sous le seuil, toutes
      branches confondues, triées par quantité croissante (les plus
      critiques en premier).
    """
    branches = Branch.query.order_by(Branch.name).all()
    per_branch = []
    low_stock_rows = []

    for branch in branches:
        rows = Stock.query.filter_by(branch_id=branch.id).all()
        low_rows = [r for r in rows if r.quantity <= low_stock_threshold]
        per_branch.append(
            {
                "branch": branch,
                "product_count": len(rows),
                "total_quantity": sum(r.quantity for r in rows),
                "low_stock_count": len(low_rows),
            }
        )
        low_stock_rows.extend(
            {
                "branch": branch,
                "product_id": r.product_id,
                "quantity": r.quantity,
            }
            for r in low_rows
        )

    low_stock_rows.sort(key=lambda r: r["quantity"])
    return per_branch, low_stock_rows


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
