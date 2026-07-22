"""API interne, lecture seule, consommée par le serveur MCP d'Erwan.

Pas de session Flask-Login ici (voir app/decorators.py::internal_token_
required) : c'est un appel serveur-à-serveur protégé par un secret
partagé, pas un utilisateur du Backoffice. Le MCP envoie toujours des
product_id/branch_id entiers (il résout les sku/texte de son côté avant
d'appeler ces routes, cf. product_mcp_server/src/resolvers.py) : on ne
refait donc aucune résolution ici, uniquement de la lecture de stock.
"""

from flask import Blueprint, jsonify, request

from app.decorators import internal_token_required
from app.models import Branch
from app.stock import service

internal_bp = Blueprint("internal", __name__, url_prefix="/api/internal")


@internal_bp.route("/health")
@internal_token_required
def health():
    return jsonify({"status": "ok"})


@internal_bp.route("/branches")
@internal_token_required
def branches():
    rows = Branch.query.order_by(Branch.id).all()
    return jsonify([{"id": b.id, "name": b.name} for b in rows])


@internal_bp.route("/stock/by-product/<int:product_id>")
@internal_token_required
def stock_by_product(product_id):
    # Pas de notion de "produit inexistant" côté Backoffice (on ne connaît
    # que des lignes de stock, pas un catalogue) : liste vide si personne
    # n'en a, jamais 404 ici.
    return jsonify(service.stock_by_product(product_id))


@internal_bp.route("/stock/by-branch/<int:branch_id>")
@internal_token_required
def stock_by_branch(branch_id):
    branch = Branch.query.get(branch_id)
    if branch is None:
        return jsonify({"error": "branch not found"}), 404

    rows = service.get_branch_stock(branch_id)
    return jsonify(
        [{"product_id": s.product_id, "quantity": s.quantity} for s in rows]
    )


@internal_bp.route("/stock/shopping-list", methods=["POST"])
@internal_token_required
def stock_shopping_list():
    body = request.get_json(silent=True) or {}
    items = body.get("items")

    if not isinstance(items, list) or not items:
        return jsonify({"error": "items must be a non-empty list"}), 400

    cleaned = []
    for item in items:
        pid = item.get("product_id") if isinstance(item, dict) else None
        qty = item.get("quantity") if isinstance(item, dict) else None
        if (
            not isinstance(pid, int)
            or pid < 1
            or not isinstance(qty, int)
            or qty < 1
        ):
            return jsonify(
                {"error": f"invalid item: {item!r}"}
            ), 400
        cleaned.append({"product_id": pid, "quantity": qty})

    return jsonify(service.check_shopping_list(cleaned))
