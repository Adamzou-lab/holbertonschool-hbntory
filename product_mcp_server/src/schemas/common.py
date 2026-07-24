"""Schemas communs a tous les outils : metadonnees, origines, enveloppe de reponse."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class DataOrigin(str, Enum):
    """Origine d'une donnee renvoyee par un tool.

    Permet au LLM (et au client) de distinguer une donnee reelle d'une
    donnee synthetique generee pour la demo.
    """

    LIVE_PRODUCT_API = "live_product_api"
    LIVE_STOCK_API = "live_stock_api"
    DERIVED_LIVE_DATA = "derived_live_data"
    SYNTHETIC_DEMO = "synthetic_demo"
    TEST_FIXTURE = "test_fixture"


class ToolMetadata(BaseModel):
    """Metadonnees standard qui accompagnent chaque reponse de tool."""

    model_config = ConfigDict(extra="forbid")

    data_origin: DataOrigin = Field(description="Origine effective de la donnee.")
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp de calcul (UTC).",
    )
    partial: bool = Field(
        default=False,
        description="True si le resultat est incomplet (donnees manquantes, etc.).",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Avertissements non-bloquants (donnees absentes, heuristiques...).",
    )
    limitations: list[str] = Field(
        default_factory=list,
        description="Limites methodologiques importantes pour l'interpretation.",
    )


class ToolResponse(BaseModel, Generic[T]):
    """Enveloppe de reponse standard pour tous les outils MCP.

    LLM : utiliser ``data`` pour les faits ; utiliser ``metadata`` pour signaler
    les limites dans la reponse textuelle.
    """

    model_config = ConfigDict(extra="forbid")

    data: T = Field(description="Donnees metier du tool.")
    metadata: ToolMetadata = Field(description="Metadonnees standard.")


# Codes d'erreur normalises (voir errors.py)
class ErrorCode(str, Enum):
    INVALID_INPUT = "invalid_input"
    NOT_FOUND = "not_found"
    UPSTREAM_TIMEOUT = "upstream_timeout"
    UPSTREAM_UNAVAILABLE = "upstream_unavailable"
    INVALID_UPSTREAM_RESPONSE = "invalid_upstream_response"
    INSUFFICIENT_DATA = "insufficient_data"
    UNAUTHORIZED = "unauthorized"
    INTERNAL_ERROR = "internal_error"


__all__ = [
    "DataOrigin",
    "ErrorCode",
    "ToolMetadata",
    "ToolResponse",
]
