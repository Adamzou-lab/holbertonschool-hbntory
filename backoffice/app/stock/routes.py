import csv
import io

from flask import (
    Blueprint,
    Response,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app import settings
from app.decorators import role_required
from app.extensions import db
from app.models import Branch
from app.products.client import get_product, get_products
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
    products = get_products(s.product_id for s in stocks)
    threshold = settings.get_setting_int(
        settings.LOW_STOCK_THRESHOLD, default=5
    )
    forecasts = {
        s.product_id: service.estimate_days_left(
            current_user.branch_id, s.product_id, s.quantity
        )
        for s in stocks
    }
    other_branches = (
        Branch.query.filter(Branch.id != current_user.branch_id)
        .order_by(Branch.name)
        .all()
    )
    return render_template(
        "stock/list.html",
        stocks=stocks,
        products=products,
        forecasts=forecasts,
        low_stock_threshold=threshold,
        other_branches=other_branches,
    )


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
            current_user.branch_id, product_id, quantity, current_user.id
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
            current_user.branch_id, product_id, quantity, current_user.id
        )
    except service.StockError as exc:
        flash(str(exc), "error")
        return redirect(url_for("stock.list_stock"))

    flash(f"Stock mis à jour : {product_id} → {entry.quantity}.", "success")
    return redirect(url_for("stock.list_stock"))


@stock_bp.route("/transfer", methods=["POST"])
@login_required
@role_required("common")
def transfer():
    product_id = _parse_positive_int(request.form.get("product_id", ""))
    quantity = _parse_positive_int(request.form.get("quantity", ""))
    target_branch_id = _parse_positive_int(
        request.form.get("target_branch_id", "")
    )

    if product_id is None or quantity is None or target_branch_id is None:
        flash(
            "Produit, quantité et branche de destination sont"
            " obligatoires.",
            "error",
        )
        return redirect(url_for("stock.list_stock"))

    try:
        service.transfer_stock(
            current_user.branch_id,
            target_branch_id,
            product_id,
            quantity,
            current_user.id,
        )
    except service.StockError as exc:
        flash(str(exc), "error")
        return redirect(url_for("stock.list_stock"))

    target = db.session.get(Branch, target_branch_id)
    target_name = target.name if target else "la branche"
    flash(
        f"{quantity}x produit #{product_id} transféré(s) vers "
        f"{target_name}.",
        "success",
    )
    return redirect(url_for("stock.list_stock"))


@stock_bp.route("/history")
@login_required
@role_required("common")
def history():
    movements = service.get_branch_history(current_user.branch_id)
    products = get_products(m.product_id for m in movements)
    return render_template(
        "stock/history.html", movements=movements, products=products
    )


@stock_bp.route("/product/<int:product_id>")
@login_required
@role_required("common")
def product_detail(product_id):
    product = get_product(product_id)
    quantity = service.get_quantity(current_user.branch_id, product_id)
    return render_template(
        "stock/product_detail.html",
        product=product,
        product_id=product_id,
        quantity=quantity,
    )


@stock_bp.route("/export.csv")
@login_required
@role_required("common")
def export_csv():
    stocks = service.get_branch_stock(current_user.branch_id)
    products = get_products(s.product_id for s in stocks)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["product_id", "name", "quantity"])
    for s in stocks:
        product = products.get(s.product_id)
        name = product.get("name", "") if product else ""
        writer.writerow([s.product_id, name, s.quantity])

    branch = current_user.branch
    raw_name = branch.name if branch else "stock"
    # secure_filename retire les caractères qui casseraient l'en-tête HTTP
    # (guillemets, ; etc.) — le nom de branche n'est pas contrôlé par un
    # attaquant aujourd'hui, mais ça évite un piège si une UI de gestion
    # des branches est ajoutée plus tard (cf. app/admin/settings.html).
    filename = secure_filename(f"{raw_name}_stock.csv")
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@stock_bp.route("/import", methods=["POST"])
@login_required
@role_required("common")
def import_csv():
    file = request.files.get("csv_file")
    if file is None or file.filename == "":
        flash("Aucun fichier sélectionné.", "error")
        return redirect(url_for("stock.list_stock"))

    try:
        # utf-8-sig plutôt que utf-8 : retire le BOM si présent (Excel en
        # ajoute un systématiquement en sauvegardant un CSV), transparent
        # pour les fichiers qui n'en ont pas.
        content = file.stream.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        flash("Fichier illisible (encodage attendu : UTF-8).", "error")
        return redirect(url_for("stock.list_stock"))

    reader = csv.DictReader(io.StringIO(content))
    fieldnames = reader.fieldnames or []
    if "product_id" not in fieldnames or "quantity" not in fieldnames:
        flash(
            "Le CSV doit contenir au minimum les colonnes"
            " product_id,quantity.",
            "error",
        )
        return redirect(url_for("stock.list_stock"))

    imported = 0
    skipped = 0
    for row in reader:
        product_id = _parse_positive_int(
            (row.get("product_id") or "").strip()
        )
        quantity = _parse_positive_int((row.get("quantity") or "").strip())
        if product_id is None or quantity is None:
            skipped += 1
            continue
        try:
            service.add_stock(
                current_user.branch_id,
                product_id,
                quantity,
                current_user.id,
            )
            imported += 1
        except service.StockError:
            skipped += 1

    message = f"{imported} ligne(s) importée(s)."
    if skipped:
        message += f" {skipped} ligne(s) ignorée(s) (invalides)."
    flash(message, "success" if imported else "error")
    return redirect(url_for("stock.list_stock"))
