import os

import click

from app.extensions import db
from app.models import ROLE_ADMIN, Branch, Stock, User

# product_id = l'id numérique interne de l'API Produit externe (pas le sku).
# Le MCP d'Erwan résout toujours le sku en id avant d'appeler le Backoffice
# (cf. product_mcp_server/src/resolvers.py, "option C") : on stocke donc
# directement l'id ici pour matcher ce contrat, sku en commentaire pour
# rester lisible humainement.
DEMO_STOCK = {
    "Branche Lyon": [
        (1, 12),   # HB-LAP-1001
        (6, 30),   # HB-KBD-4101
        (8, 25),   # HB-MSE-4201
    ],
    "Branche Paris": [
        (3, 8),    # HB-MON-2101
        (15, 14),  # HB-SSD-7101
        (9, 5),    # HB-CAM-5101
    ],
    "Branche Marseille": [
        (12, 3),   # HB-RTR-6101
        (17, 40),  # HB-USB-7201
        (22, 6),   # HB-CHR-9101
    ],
}


def register_cli(app):
    @app.cli.command("seed")
    def seed():
        """Crée l'admin unique, des branches et du stock de démo."""
        admin_email = os.environ.get("ADMIN_EMAIL", "admin@zaiko.local")
        admin_password = os.environ.get("ADMIN_PASSWORD")

        if User.query.filter_by(role=ROLE_ADMIN).first() is None:
            if not admin_password:
                click.echo(
                    "ADMIN_PASSWORD non défini — mot de passe de dev par "
                    "défaut utilisé, à changer avant toute démo/prod."
                )
                admin_password = "changeme123"
            admin = User(
                email=admin_email,
                username="Admin",
                role=ROLE_ADMIN,
                is_active=True,
            )
            admin.set_password(admin_password)
            db.session.add(admin)
            click.echo(f"Admin créé : {admin_email}")
        else:
            click.echo("Un admin existe déjà, rien à faire.")

        if Branch.query.count() == 0:
            for name in DEMO_STOCK:
                db.session.add(Branch(name=name))
            click.echo("Branches de démo créées : " + ", ".join(DEMO_STOCK))
        db.session.commit()

        if Stock.query.count() == 0:
            for branch_name, items in DEMO_STOCK.items():
                branch = Branch.query.filter_by(name=branch_name).first()
                for product_id, quantity in items:
                    db.session.add(
                        Stock(
                            branch_id=branch.id,
                            product_id=product_id,
                            quantity=quantity,
                        )
                    )
            click.echo(
                "Stock de démo créé (product_id réels de l'API Produit)."
            )

        db.session.commit()
