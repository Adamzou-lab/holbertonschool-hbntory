"""Exceptions metier et mapping vers les erreurs MCP.

Les modules du MCP lèvent des exceptions metier (ProductApiError, StockApiError)
avec un message deja exploitable par l'agent IA. Les tools les convertissent
en ToolError cote serveur MCP.
"""

from __future__ import annotations

from mcp.server.fastmcp.exceptions import ToolError


class MCPServiceError(Exception):
    """Base pour toutes les erreurs metier du MCP."""


class ProductApiError(MCPServiceError):
    """Erreur renvoyee par l'API Produit externe (4xx/5xx, reseau, etc.)."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class StockApiError(MCPServiceError):
    """Erreur renvoyee par l'API interne du Backoffice."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ResolverError(MCPServiceError):
    """Erreur de normalisation/normalisation d'un identifiant produit."""


# --- Mapping vers ToolError ---


def to_tool_error(exc: MCPServiceError) -> ToolError:
    """Convertit une exception metier en ToolError avec un message clair.

    Le message est volontairement formulé pour etre transmis tel quel
    a l'agent IA, qui doit le relayer ou composer autour.
    """
    if isinstance(exc, ProductApiError):
        if exc.status_code == 404:
            return ToolError(str(exc))
        return ToolError("External product API unavailable")
    if isinstance(exc, StockApiError):
        if exc.status_code == 403:
            return ToolError("Internal stock API denied request")
        if exc.status_code == 404:
            return ToolError(str(exc))
        return ToolError("Internal stock API unreachable")
    if isinstance(exc, ResolverError):
        return ToolError(str(exc))
    return ToolError(str(exc))
