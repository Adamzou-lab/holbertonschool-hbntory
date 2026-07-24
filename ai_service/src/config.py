"""Configuration du Service IA via variables d'environnement."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings charges depuis l'environnement + .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Provider LLM ---

    llm_provider: str = Field(
        default="anthropic",
        description="Fournisseur LLM (anthropic, openai, gemini, ollama, etc.).",
    )
    llm_model: str = Field(
        default="claude-3-5-sonnet-latest",
        description="Nom du modele chez le fournisseur.",
    )

    # NB : les cles API elles-memes sont lues directement par PydanticAI
    # via les variables standard (ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.).
    # Pas besoin de les declarer ici.

    # --- Connexion MCP ---

    mcp_server_url: str = Field(
        default="http://localhost:8000/mcp",
        description="URL du serveur MCP HBntory (Bloc 2).",
    )

    # --- Serveur IA ---

    ai_host: str = Field(default="0.0.0.0", description="Host d'ecoute.")
    ai_port: int = Field(default=8080, ge=1, le=65535, description="Port d'ecoute.")

    log_level: str = Field(default="INFO", description="Niveau de log.")

    request_timeout_seconds: float = Field(
        default=30.0,
        ge=1.0,
        description="Timeout pour un appel /query (incluant la boucle agent).",
    )

    # --- Securite / debug ---

    expose_tools_endpoint: bool = Field(
        default=True,
        description="Si true, expose GET /tools (debug). A desactiver en prod.",
    )

    internal_token: str | None = Field(
        default=None,
        alias="AI_INTERNAL_TOKEN",
        description="Token attendu pour /internal/query. Si None, l'endpoint est ferme.",
    )


def get_settings() -> Settings:
    return Settings()
