from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.auth import service

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/")
def index():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    if current_user.is_admin:
        return redirect(url_for("admin.users_list"))
    return redirect(url_for("stock.list_stock"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("auth.index"))

    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        success, result = service.attempt_login(email, password)
        if success:
            return redirect(url_for("auth.index"))
        error = result

    return render_template("auth/login.html", error=error)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    service.logout()
    return redirect(url_for("auth.login"))
