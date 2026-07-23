"""Configuration du serveur MCP via variables d'environnement.

Toutes les valeurs proviennent de l'environnement (ou d'un fichier .env local).
Aucune valeur n'est codee en dur.
"""

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

    products_api_base_url: str = Field(
        default="http://localhost:5001",
        description="URL de base de l'API Produit externe (Docker fourni).",
    )

    backoffice_base_url: str = Field(
        default="http://localhost:5000",
        description="URL de base du Backoffice HBntory (routes internes).",
    )

    backoffice_internal_token: str = Field(
        default="change-me",
        description="Token partage envoye en header X-Internal-Token au Backoffice.",
    )

    mcp_host: str = Field(default="0.0.0.0", description="Host d'ecoute MCP.")
    mcp_port: int = Field(default=8000, ge=1, le=65535, description="Port d'ecoute MCP.")

    log_level: str = Field(default="INFO", description="Niveau de log (DEBUG/INFO/WARNING/ERROR).")

    request_timeout_seconds: float = Field(
        default=10.0,
        ge=1.0,
        description="Timeout HTTP pour les appels sortants (API Produit et Backoffice).",
    )


def get_settings() -> Settings:
    """Fabrique simple. Les tests peuvent monkey-patcher l'environnement."""
    return Settings()
