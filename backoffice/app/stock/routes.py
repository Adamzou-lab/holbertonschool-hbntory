from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.decorators import role_required
from app.stock import service

stock_bp = Blueprint("stock", __name__, url_prefix="/stock")


def _parse_positive_int(raw):
    if raw is None or not raw.isdigit():
        return None
    value = int(raw)
    return value if value > 0 else None


@stock_bp.route("")
@login_required
@role_required("common")
def list_stock():
    stocks = service.get_branch_stock(current_user.branch_id)
    return render_template("stock/list.html", stocks=stocks)


@stock_bp.route("/add", methods=["POST"])
@login_required
@role_required("common")
def add_stock():
    product_id = _parse_positive_int(request.form.get("product_id", ""))
    quantity = _parse_positive_int(request.form.get("quantity", ""))

    if product_id is None or quantity is None:
        flash(
            "Identifiant produit et quantité doivent être des entiers"
            " positifs.",
            "error",
        )
        return redirect(url_for("stock.list_stock"))

    try:
        entry = service.add_stock(
            current_user.branch_id, product_id, quantity
        )
    except service.StockError as exc:
        flash(str(exc), "error")
        return redirect(url_for("stock.list_stock"))

    flash(f"Stock mis à jour : {product_id} → {entry.quantity}.", "success")
    return redirect(url_for("stock.list_stock"))


@stock_bp.route("/remove", methods=["POST"])
@login_required
@role_required("common")
def remove_stock():
    product_id = _parse_positive_int(request.form.get("product_id", ""))
    quantity = _parse_positive_int(request.form.get("quantity", ""))

    if product_id is None or quantity is None:
        flash(
            "Identifiant produit et quantité doivent être des entiers"
            " positifs.",
            "error",
        )
        return redirect(url_for("stock.list_stock"))

    try:
        entry = service.remove_stock(
            current_user.branch_id, product_id, quantity
        )
    except service.StockError as exc:
        flash(str(exc), "error")
        return redirect(url_for("stock.list_stock"))

    flash(f"Stock mis à jour : {product_id} → {entry.quantity}.", "success")
    return redirect(url_for("stock.list_stock"))
