"""HBntory Product MCP Server.

Bridge entre le Service IA et :
  - l'API Produit externe (lecture seule, fournie en Docker) ;
  - l'API interne du Backoffice HBntory (lecture seule, expose le stock).

Les outils exposes sont read-only sur le stock. Les mutations (add/remove)
restent dans le Backoffice, derriere auth + role + controle de branche.
"""

__version__ = "0.1.0"
