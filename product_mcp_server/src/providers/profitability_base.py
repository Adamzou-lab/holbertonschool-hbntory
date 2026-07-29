"""Interfaces providers pour Phase 3 (profitabilite)."""

from __future__ import annotations

from typing import Protocol

from ..schemas.margin import ProfitabilityData


class ProfitabilityDataProvider(Protocol):
    """Source d'evenements ventes + achats pour le calcul de marges.

    En MVP, seul FixtureProfitabilityProvider est livre (donnees
    synthetiques). Si une source reelle devient disponible, ajouter une
    HttpProfitabilityProvider qui respecte le meme contrat.
    """

    async def get_events(
        self,
        *,
        days: int,
        seed: int | None = None,
    ) -> ProfitabilityData:
        ...


__all__ = ["ProfitabilityDataProvider"]
