from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db

ROLE_ADMIN = "admin"
ROLE_COMMON = "common"


def _utcnow():
    return datetime.now(timezone.utc)


class Branch(db.Model):
    __tablename__ = "branches"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)

    users = db.relationship("User", back_populates="branch")
    stocks = db.relationship(
        "Stock", back_populates="branch", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Branch {self.name}>"


class User(UserMixin, db.Model):
    __tablename__ = "users"
    __table_args__ = (
        db.CheckConstraint(
            f"role IN ('{ROLE_ADMIN}', '{ROLE_COMMON}')", name="ck_users_role"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    # Pas utilisé pour se connecter (c'est l'email qui sert d'identifiant) :
    # juste un nom affiché à côté de la branche dans l'UI, plus lisible
    # qu'une adresse email dans la sidebar ou une liste d'utilisateurs.
    username = db.Column(db.String(80), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_COMMON)
    branch_id = db.Column(
        db.Integer, db.ForeignKey("branches.id"), nullable=True
    )
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    branch = db.relationship("Branch", back_populates="users")

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    @property
    def is_admin(self):
        return self.role == ROLE_ADMIN

    @property
    def is_common(self):
        return self.role == ROLE_COMMON

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


class Stock(db.Model):
    __tablename__ = "stocks"
    __table_args__ = (
        db.CheckConstraint(
            "quantity >= 0", name="ck_stocks_quantity_non_negative"
        ),
        db.UniqueConstraint(
            "branch_id", "product_id", name="uq_stocks_branch_product"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    branch_id = db.Column(
        db.Integer, db.ForeignKey("branches.id"), nullable=False
    )
    product_id = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    branch = db.relationship("Branch", back_populates="stocks")

    def __repr__(self):
        return f"<Stock {self.product_id}@{self.branch_id}: {self.quantity}>"


MOVEMENT_ADD = "add"
MOVEMENT_REMOVE = "remove"
MOVEMENT_TRANSFER_IN = "transfer_in"
MOVEMENT_TRANSFER_OUT = "transfer_out"
MOVEMENT_TYPES = (
    MOVEMENT_ADD,
    MOVEMENT_REMOVE,
    MOVEMENT_TRANSFER_IN,
    MOVEMENT_TRANSFER_OUT,
)


class StockMovement(db.Model):
    """Journal immuable des mouvements de stock (ajouté hors MVP initial,
    cf. docs/mvp.md) : chaque add/remove/transfert laisse une trace, utilisée
    à la fois pour l'écran "Historique" et pour estimer les prévisions de
    rupture (app/stock/service.py:estimate_days_left)."""

    __tablename__ = "stock_movements"
    __table_args__ = (
        db.CheckConstraint(
            "movement_type IN ('add', 'remove', 'transfer_in', 'transfer_out')",
            name="ck_stock_movements_type",
        ),
        db.CheckConstraint(
            "quantity > 0", name="ck_stock_movements_quantity_positive"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    branch_id = db.Column(
        db.Integer, db.ForeignKey("branches.id"), nullable=False
    )
    product_id = db.Column(db.Integer, nullable=False)
    movement_type = db.Column(db.String(20), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    # Renseigné uniquement pour transfer_in/transfer_out : l'autre branche
    # impliquée dans le transfert.
    related_branch_id = db.Column(
        db.Integer, db.ForeignKey("branches.id"), nullable=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )
    created_at = db.Column(db.DateTime, default=_utcnow)

    branch = db.relationship("Branch", foreign_keys=[branch_id])
    related_branch = db.relationship(
        "Branch", foreign_keys=[related_branch_id]
    )
    user = db.relationship("User")

    def __repr__(self):
        return (
            f"<StockMovement {self.movement_type} "
            f"{self.quantity}x#{self.product_id}@{self.branch_id}>"
        )


ADMIN_ACTION_CREATED = "user_created"
ADMIN_ACTION_UPDATED = "user_updated"
ADMIN_ACTION_ACTIVATED = "user_activated"
ADMIN_ACTION_DEACTIVATED = "user_deactivated"
ADMIN_ACTION_TYPES = (
    ADMIN_ACTION_CREATED,
    ADMIN_ACTION_UPDATED,
    ADMIN_ACTION_ACTIVATED,
    ADMIN_ACTION_DEACTIVATED,
)


class AdminAction(db.Model):
    """Journal des actions d'admin sur les comptes utilisateurs (ajouté
    hors MVP initial, cf. docs/mvp.md) : qui a créé/modifié/activé/
    désactivé quel compte, et quand. Traçabilité pure — jamais consulté
    pour autoriser ou refuser quoi que ce soit (contrairement à
    role_required), juste pour répondre à "qui a fait quoi" en cas de
    besoin."""

    __tablename__ = "admin_actions"
    __table_args__ = (
        db.CheckConstraint(
            "action_type IN ("
            "'user_created', 'user_updated', "
            "'user_activated', 'user_deactivated'"
            ")",
            name="ck_admin_actions_type",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )
    target_user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )
    action_type = db.Column(db.String(30), nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow)

    actor = db.relationship("User", foreign_keys=[actor_id])
    target_user = db.relationship("User", foreign_keys=[target_user_id])

    def __repr__(self):
        return f"<AdminAction {self.action_type} on #{self.target_user_id}>"


class AppSetting(db.Model):
    """Paramètres techniques éditables par l'admin sans redéploiement
    (ajouté hors MVP initial, cf. docs/mvp.md) : clé/valeur simple, lus via
    app/settings.py:get_setting(key, default)."""

    __tablename__ = "app_settings"

    key = db.Column(db.String(80), primary_key=True)
    value = db.Column(db.String(255), nullable=True)

    def __repr__(self):
        return f"<AppSetting {self.key}={self.value!r}>"
