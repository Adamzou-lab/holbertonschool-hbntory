import os


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
