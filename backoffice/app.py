"""
Point d'entrée Flask - Pôle A.

But : brancher models + auth + decorators + stock_service ensemble,
et exposer quelques routes minimales pour tester en vrai (via curl/Postman)
que l'authentification et les autorisations fonctionnent en HTTP.

Lancer avec : flask --app app run --debug
"""

import os
from flask import Flask, request, jsonify
from flask_login import login_required, current_user

from models import db, Branch, Stock
from auth import init_auth, attempt_login, logout
from decorators import admin_required, common_required, same_branch_required
from stock_service import add_stock, remove_stock, get_branch_stock, StockError

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///hbtory.db"
)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

db.init_app(app)
init_auth(app)


# --- Auth ---

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    ok, result = attempt_login(username, password)
    if not ok:
        return jsonify({"error": result}), 401

    return jsonify({"message": "Connecté", "role": result.role})


@app.route("/logout", methods=["POST"])
@login_required
def logout_route():
    logout()
    return jsonify({"message": "Déconnecté"})


# --- Admin : lecture rapide des branches (juste pour tester le rôle) ---

@app.route("/admin/branches", methods=["GET"])
@admin_required
def list_branches():
    branches = Branch.query.all()
    return jsonify([{"id": b.id, "name": b.name} for b in branches])


# --- Common user : stock de sa propre branche ---

@app.route("/stock/<int:branch_id>", methods=["GET"])
@common_required
@same_branch_required(lambda branch_id: branch_id)
def view_stock(branch_id):
    items = get_branch_stock(branch_id)
    return jsonify(
        [{"product_id": s.product_id, "quantity": s.quantity} for s in items]
    )


@app.route("/stock/<int:branch_id>/add", methods=["POST"])
@common_required
@same_branch_required(lambda branch_id: branch_id)
def add_stock_route(branch_id):
    data = request.get_json()
    try:
        row = add_stock(branch_id, data["product_id"], data["amount"])
        return jsonify({"product_id": row.product_id, "quantity": row.quantity})
    except StockError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/stock/<int:branch_id>/remove", methods=["POST"])
@common_required
@same_branch_required(lambda branch_id: branch_id)
def remove_stock_route(branch_id):
    data = request.get_json()
    try:
        row = remove_stock(branch_id, data["product_id"], data["amount"])
        return jsonify({"product_id": row.product_id, "quantity": row.quantity})
    except StockError as e:
        return jsonify({"error": str(e)}), 400


# --- Route de debug, pratique pour vérifier qui est connecté ---

@app.route("/whoami", methods=["GET"])
@login_required
def whoami():
    return jsonify(
        {
            "username": current_user.username,
            "role": current_user.role,
            "branch_id": current_user.branch_id,
        }
    )


if __name__ == "__main__":
    app.run(debug=True)
