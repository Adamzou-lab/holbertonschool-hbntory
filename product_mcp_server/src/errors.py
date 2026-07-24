"""Exceptions metier et codes d'erreur normalises (E1).

Les tools du MCP lèvent des exceptions metier ; le mapping ToolError
conserve uniquement le code + un message user-friendly, jamais de stack
trace vers le LLM ou le client.
"""

from __future__ import annotations

import logging

from mcp.server.fastmcp.exceptions import ToolError

from .schemas.common import ErrorCode

logger = logging.getLogger(__name__)


class MCPServiceError(Exception):
    """Base pour toutes les erreurs metier du MCP."""

    code: ErrorCode = ErrorCode.INTERNAL_ERROR

    def __init__(self, message: str, *, code: ErrorCode | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class ProductApiError(MCPServiceError):
    code = ErrorCode.UPSTREAM_UNAVAILABLE

    def __init__(self, message: str, *, code: ErrorCode | None = None, status_code: int | None = None) -> None:
        super().__init__(message, code=code)
        self.status_code = status_code


class StockApiError(MCPServiceError):
    code = ErrorCode.UPSTREAM_UNAVAILABLE

    def __init__(self, message: str, *, code: ErrorCode | None = None, status_code: int | None = None) -> None:
        super().__init__(message, code=code)
        self.status_code = status_code


class InvalidInputError(MCPServiceError):
    code = ErrorCode.INVALID_INPUT


class NotFoundError(MCPServiceError):
    code = ErrorCode.NOT_FOUND


class InsufficientDataError(MCPServiceError):
    code = ErrorCode.INSUFFICIENT_DATA


class UnauthorizedError(MCPServiceError):
    code = ErrorCode.UNAUTHORIZED


class ResolverError(MCPServiceError):
    """Erreur liee a la normalisation d'un identifiant produit (option C)."""

    code = ErrorCode.INVALID_INPUT


class InvalidUpstreamResponse(MCPServiceError):
    """La reponse d'un upstream n'est pas conforme au schema attendu."""

    code = ErrorCode.INVALID_UPSTREAM_RESPONSE


# --- Mapping vers ToolError ---


def to_tool_error(exc: MCPServiceError) -> ToolError:
    """Convertit une exception metier en ToolError avec code + message clair.

    Aucune stack trace n'est exposee. Le code peut etre lu cote agent.
    """
    msg = f"[{exc.code.value}] {exc}"
    if isinstance(exc, ProductApiError):
        if exc.status_code == 404:
            return ToolError(f"[{ErrorCode.NOT_FOUND.value}] {exc}")
    if isinstance(exc, StockApiError):
        if exc.status_code == 403:
            return ToolError(f"[{ErrorCode.UNAUTHORIZED.value}] {exc}")
        if exc.status_code == 404:
            return ToolError(f"[{ErrorCode.NOT_FOUND.value}] {exc}")
    return ToolError(msg)


__all__ = [
    "MCPServiceError",
    "ProductApiError",
    "StockApiError",
    "InvalidInputError",
    "NotFoundError",
    "InsufficientDataError",
    "UnauthorizedError",
    "to_tool_error",
    "ErrorCode",
]
