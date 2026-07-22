"""
Modèles SQLAlchemy pour HBtory - Pôle A.

Règle d'or : aucune information produit n'est stockée ici.
Stock.product_id n'est qu'un identifiant, tout le reste vient de l'API Produit.
"""

from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()


class Branch(db.Model):
    __tablename__ = "branches"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

    users = db.relationship("User", back_populates="branch")
    stock_items = db.relationship("Stock", back_populates="branch")

    def __repr__(self):
        return f"<Branch {self.id} {self.name}>"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    # "admin" ou "common"
    role = db.Column(db.String(20), nullable=False, default="common")

    # null uniquement pour l'admin
    branch_id = db.Column(db.Integer, db.ForeignKey("branches.id"), nullable=True)

    # soft-delete : jamais de suppression physique
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    branch = db.relationship("Branch", back_populates="users")

    # --- Helpers de rôle, utilisés partout dans les decorators ---
    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_common(self):
        return self.role == "common"

    # Note : UserMixin fournit par défaut une propriété is_active = True.
    # Comme on définit ici notre propre colonne is_active, elle prend le dessus :
    # Flask-Login lit automatiquement current_user.is_active, donc un user
    # soft-deleted (is_active=False) sera rejeté par Flask-Login lui-même.

    def __repr__(self):
        return f"<User {self.id} {self.username} ({self.role})>"


class Stock(db.Model):
    __tablename__ = "stock"

    id = db.Column(db.Integer, primary_key=True)
    branch_id = db.Column(db.Integer, db.ForeignKey("branches.id"), nullable=False)

    # Uniquement l'identifiant retourné par l'API Produit externe.
    product_id = db.Column(db.Integer, nullable=False)

    quantity = db.Column(db.Integer, nullable=False, default=0)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    branch = db.relationship("Branch", back_populates="stock_items")

    __table_args__ = (
        # Une seule ligne de stock par (branche, produit)
        db.UniqueConstraint("branch_id", "product_id", name="uq_branch_product"),
        # Ceinture et bretelles : contrainte SQL en plus de la validation applicative
        db.CheckConstraint("quantity >= 0", name="ck_quantity_non_negative"),
    )

    def __repr__(self):
        return f"<Stock branch={self.branch_id} product={self.product_id} qty={self.quantity}>"