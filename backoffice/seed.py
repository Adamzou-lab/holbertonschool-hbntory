"""
Script d'initialisation de la base - Pôle A.

Usage : python seed.py

Crée :
- 1 admin (mot de passe hashé, jamais en clair)
- 2 branches
- du stock de test pour pouvoir tester le MCP / Service IA ensuite
"""

import os
from flask import Flask
from models import db, Branch, User, Stock
from auth import hash_password

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///hbtory.db"
)
db.init_app(app)

with app.app_context():
    db.create_all()

    if User.query.filter_by(username="admin").first() is None:
        admin = User(
            username="admin",
            password_hash=hash_password("ChangeMe123!"),  # à changer en prod
            role="admin",
            branch_id=None,
            is_active=True,
        )
        db.session.add(admin)

    branch_paris = Branch.query.filter_by(name="Paris").first()
    if branch_paris is None:
        branch_paris = Branch(name="Paris")
        db.session.add(branch_paris)

    branch_lyon = Branch.query.filter_by(name="Lyon").first()
    if branch_lyon is None:
        branch_lyon = Branch(name="Lyon")
        db.session.add(branch_lyon)

    db.session.commit()  # commit pour avoir les IDs des branches

    if User.query.filter_by(username="employe_paris").first() is None:
        employe_paris = User(
            username="employe_paris",
            password_hash=hash_password("Password123!"),
            role="common",
            branch_id=branch_paris.id,
            is_active=True,
        )
        db.session.add(employe_paris)

    # Stock de test : product_id correspond à des IDs qui doivent exister
    # côté API Produit (Docker) pour que le test soit cohérent bout-en-bout.
    sample_stock = [
        (branch_paris.id, 1, 50),
        (branch_paris.id, 2, 10),
        (branch_lyon.id, 1, 5),
        (branch_lyon.id, 3, 30),
    ]
    for branch_id, product_id, quantity in sample_stock:
        exists = Stock.query.filter_by(
            branch_id=branch_id, product_id=product_id
        ).first()
        if exists is None:
            db.session.add(
                Stock(branch_id=branch_id, product_id=product_id, quantity=quantity)
            )

    db.session.commit()
    print("Base initialisée : admin / ChangeMe123! + 2 branches + stock de test.")
