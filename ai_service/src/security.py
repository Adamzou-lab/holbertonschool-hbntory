"""Securite du Service IA : protection de l'endpoint interne.

L'endpoint ``/internal/query`` necessite un header ``X-Internal-Token``
egal a la valeur de ``settings.internal_token``. Si non defini, la
protection est strict (tout appel refuse).
"""

from __future__ import annotations

import hmac

from fastapi import HTTPException, Request, status


def _safe_eq(a: str, b: str) -> bool:
    """Comparaison resistant aux timing attacks."""
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def require_internal_token(request: Request, expected: str | None) -> None:
    """Verifie le header X-Internal-Token. Leve 401 ou 503 selon le cas."""
    if not expected:
        # Pas de token configure = endpoint strictement ferme.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal endpoint not configured.",
        )
    provided = request.headers.get("X-Internal-Token")
    if not provided or not _safe_eq(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Internal-Token.",
        )


__all__ = ["require_internal_token"]
