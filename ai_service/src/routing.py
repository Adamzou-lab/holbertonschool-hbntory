"""Intentions + decisions structurees pour le routeur du Service IA."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Intent(str, Enum):
    INVENTORY = "inventory"
    ANALYTICS = "analytics"
    FORECAST = "forecast"
    MARGIN = "margin"
    OUT_OF_SCOPE = "out_of_scope"


class RoutingDecision(BaseModel):
    """Sortie structuree du routeur LLM."""

    model_config = ConfigDict(extra="forbid")

    intent: Intent
    confidence: float = Field(ge=0, le=1)
    reason_code: str = Field(description="Code court expliquant la decision (snake_case).")


__all__ = ["Intent", "RoutingDecision"]
