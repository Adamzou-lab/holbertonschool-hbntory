from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import login_required

from app import settings
from app.decorators import role_required
from app.extensions import db
from app.models import ROLE_COMMON, Branch, User
from app.products.client import get_products
from app.stock import service as stock_service

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/dashboard")
@login_required
@role_required("admin")
def dashboard():
    threshold = settings.get_setting_int(
        settings.LOW_STOCK_THRESHOLD, default=5
    )
    per_branch, low_stock_rows = stock_service.dashboard_overview(threshold)
    products = get_products(row["product_id"] for row in low_stock_rows)
    return render_template(
        "admin/dashboard.html",
        per_branch=per_branch,
        low_stock_rows=low_stock_rows,
        products=products,
        low_stock_threshold=threshold,
    )


@admin_bp.route("/users")
@login_required
@role_required("admin")
def users_list():
    users = User.query.filter_by(role=ROLE_COMMON).order_by(User.email).all()
    return render_template("admin/users.html", users=users)


@admin_bp.route("/users/new", methods=["GET", "POST"])
@login_required
@role_required("admin")
def user_new():
    branches = Branch.query.order_by(Branch.name).all()
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        branch_id = request.form.get("branch_id") or None

        if not email or not username or not password:
            error = "Email, nom affiché et mot de passe sont obligatoires."
        elif not branch_id:
            error = "Un common user doit être rattaché à une branche."
        elif User.query.filter_by(email=email).first() is not None:
            error = "Cet email est déjà utilisé."
        else:
            user = User(
                email=email,
                username=username,
                role=ROLE_COMMON,
                branch_id=int(branch_id),
                is_active=True,
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash("Utilisateur créé.", "success")
            return redirect(url_for("admin.users_list"))

    return render_template(
        "admin/user_form.html", branches=branches, user=None, error=error
    )


@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin")
def user_edit(user_id):
    user = User.query.filter_by(id=user_id, role=ROLE_COMMON).first_or_404()
    branches = Branch.query.order_by(Branch.name).all()
    error = None

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        username = request.form.get("username", "").strip()
        branch_id = request.form.get("branch_id") or None
        new_password = request.form.get("password", "")

        if not email or not username:
            error = "Email et nom affiché sont obligatoires."
        elif not branch_id:
            error = "Un common user doit être rattaché à une branche."
        elif (
            User.query.filter(User.email == email, User.id != user.id).first()
            is not None
        ):
            error = "Cet email est déjà utilisé."
        else:
            user.email = email
            user.username = username
            user.branch_id = int(branch_id)
            if new_password:
                user.set_password(new_password)
            db.session.commit()
            flash("Utilisateur mis à jour.", "success")
            return redirect(url_for("admin.users_list"))

    return render_template(
        "admin/user_form.html", branches=branches, user=user, error=error
    )


@admin_bp.route("/users/<int:user_id>/toggle-active", methods=["POST"])
@login_required
@role_required("admin")
def user_toggle_active(user_id):
    user = User.query.filter_by(id=user_id, role=ROLE_COMMON).first_or_404()
    user.is_active = not user.is_active
    db.session.commit()
    flash(
        "Utilisateur réactivé."
        if user.is_active
        else "Utilisateur désactivé (soft-delete).",
        "success",
    )
    return redirect(url_for("admin.users_list"))


@admin_bp.route("/settings", methods=["GET", "POST"])
@login_required
@role_required("admin")
def settings_page():
    error = None
    if request.method == "POST":
        threshold_raw = request.form.get("low_stock_threshold", "").strip()
        api_url = request.form.get("products_api_base_url", "").strip()

        if threshold_raw and not threshold_raw.isdigit():
            error = "Le seuil de stock faible doit être un entier positif."
        else:
            settings.set_setting(
                settings.LOW_STOCK_THRESHOLD, threshold_raw or None
            )
            settings.set_setting(
                settings.PRODUCTS_API_BASE_URL, api_url or None
            )
            flash("Paramètres mis à jour.", "success")
            return redirect(url_for("admin.settings_page"))

    return render_template(
        "admin/settings.html",
        low_stock_threshold=settings.get_setting(
            settings.LOW_STOCK_THRESHOLD, default=""
        ),
        products_api_base_url=settings.get_setting(
            settings.PRODUCTS_API_BASE_URL, default=""
        ),
        default_products_api_base_url=current_app.config[
            "PRODUCTS_API_BASE_URL"
        ],
        error=error,
    )
