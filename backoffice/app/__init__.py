from flask import Flask

from app.config import Config
from app.extensions import csrf, db, login_manager, migrate


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from app.auth.routes import auth_bp
    from app.admin.routes import admin_bp
    from app.stock.routes import stock_bp
    from app.internal.routes import internal_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(stock_bp)
    app.register_blueprint(internal_bp)

    # Appels serveur-à-serveur (MCP -> Backoffice), authentifiés par
    # X-Internal-Token (voir app/decorators.py::internal_token_required),
    # pas par session cookie : pas de csrf_token possible côté client MCP.
    csrf.exempt(internal_bp)

    from app.cli import register_cli

    register_cli(app)

    return app
