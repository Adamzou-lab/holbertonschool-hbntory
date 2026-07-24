import os

from sqlalchemy.pool import StaticPool


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(os.path.dirname(os.path.dirname(__file__)), "backoffice.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Token partagé attendu dans le header X-Internal-Token par les routes
    # /api/internal/... (consommées par le serveur MCP d'Erwan, pas de
    # session Flask-Login pour ces routes machine-à-machine). Défaut
    # identique à product_mcp_server/.env.example côté MCP pour que les
    # deux services matchent en dev sans configuration supplémentaire.
    BACKOFFICE_INTERNAL_TOKEN = os.environ.get(
        "BACKOFFICE_INTERNAL_TOKEN", "change-me-shared-secret"
    )

    # API Produit externe (lecture seule, cf. docs/architecture.md §5).
    # Même défaut que product_mcp_server/.env.example côté MCP pour matcher
    # en dev sans configuration supplémentaire.
    PRODUCTS_API_BASE_URL = os.environ.get(
        "PRODUCTS_API_BASE_URL", "http://localhost:5001"
    )


class TestConfig(Config):
    """Config utilisée par la suite de tests (tests/conftest.py).

    SQLite en mémoire + StaticPool : sans ça, chaque nouvelle connexion
    ouverte par le pool par défaut de SQLAlchemy verrait une base en
    mémoire différente (vide), et les tables créées dans un fixture
    n'existeraient plus pour la requête suivante.
    """

    TESTING = True
    SECRET_KEY = "test-secret"
    # Les tests postent directement via le client de test sans passer par
    # un vrai formulaire rendu (donc sans csrf_token) — désactiver la
    # vérification ici, pas en prod (voir Config.WTF_CSRF_ENABLED, absent
    # = activé par défaut par Flask-WTF).
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {
        "poolclass": StaticPool,
        "connect_args": {"check_same_thread": False},
    }
    BACKOFFICE_INTERNAL_TOKEN = "test-internal-token"
    # Port réservé (jamais un vrai service dessus) : les tests doivent
    # rester déterministes, pas dépendre de si la vraie API Produit
    # tourne ou non sur la machine de dev au moment du run.
    PRODUCTS_API_BASE_URL = "http://127.0.0.1:1"
