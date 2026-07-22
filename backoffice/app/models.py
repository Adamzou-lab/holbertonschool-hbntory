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
    product_id = db.Column(db.String(64), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    branch = db.relationship("Branch", back_populates="stocks")

    def __repr__(self):
        return f"<Stock {self.product_id}@{self.branch_id}: {self.quantity}>"
