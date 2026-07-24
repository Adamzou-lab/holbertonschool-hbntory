# Limitations du serveur MCP HBntory (Bloc 2)

Ce document liste explicitement ce que le serveur MCP **ne fait pas**, pour
eviter toute presentation trompeuse au jury ou aux utilisateurs finaux.

## 1. Read-only strict

- Aucun outil n'ecrit dans une base de donnees.
- Aucun outil ne declenche de commande fournisseur.
- Aucun outil ne modifie un prix, un produit, ou une branche.
- Les mutations (add/remove stock) restent dans le Backoffice HBntory, sous
  authentification + controle de role + branche + check quantite >= 0.

## 2. Pas d'acces SQL

- Le MCP utilise uniquement des clients HTTP (API Produit externe, API interne Backoffice).
- Aucun driver SQLAlchemy, aucun acces direct a la DB HBntory.
- Les donnees agregees (catalogue complet, fournisseurs) passent par un cache TTL
  en memoire (pas Redis, pas d'infra externe).

## 3. Donnees synthetiques pour Margin (Phase 3)

- Les outils `compute_product_margin`, `identify_most_profitable`,
  `compute_supplier_cost`, `analyze_storage_efficiency` reposent sur des
  evenements **generes localement** (FixtureProfitabilityProvider).
- Aucune source reelle (POS, ERP) n'est integree.
- Toutes les reponses portent `data_origin="synthetic_demo"`.
- Les chiffres ne refletent aucune activite commerciale reelle.

## 4. Pas de "vraie" prediction (Phase 2)

- `analyze_stock_trend` utilise une regression lineaire simple. Pas de SARIMA,
  pas de Prophet, pas de LSTM. Pour 3-7 points de donnees, la regression n'a
  presque aucun pouvoir predictif.
- `forecast_stockout_and_reorder` extrapole une baisse lineaire. Si la consommation
  est reellement non-lineaire (promotions, saisonnalite, rupture d'approvisionnement),
  la prediction est fausse.
- `detect_seasonal_pattern` utilise l'autocorrelation sur 7/30/90 jours. Pas d'analyse
  spectrale, pas de decomposition STL.
- Les donnees proviennent d'une fixture deterministe. Pas d'historique reel cote
  Backoffice (la table `stock_history` n'est pas creee par ce Bloc).

## 5. Pas d'analyse des couts reels

- `compute_supplier_cost` agrege les couts d'achat **des evenements synthetiques**.
  Les couts reels (negociation fournisseur, delais, transport) ne sont pas accessibles.
- `analyze_storage_efficiency` combine complexite (reelle) et marge (synthetique). La
  recommandation finale est **indicative**, pas une decision automatique.

## 6. Heuristiques versionnees

- `assess_storage_complexity` utilise `heuristic_v1` (poids 40% + categorie 30%
  + discontinue 20% + tags 10%). Toute evolution doit incrementer la version et
  mettre a jour le tool.
- `analyze_stock_trend` considere un mouvement stable (pente de regression).
  Pas de detection de rupture structurelle.

## 7. Pas de politique de confidentialite implementable

- Le serveur MCP suppose que l'API interne Backoffice respecte deja les ACL.
- Il ajoute un header `X-Internal-Token` partage, mais ne gere pas OAuth, pas de
  rate-limiting par utilisateur, pas d'audit des appels.

## 8. Pas de monitoring

- Pas de Prometheus, OpenTelemetry, ou health check avance.
- Une seule route `/health` qui renvoie `{"status": "ok"}`.

## 9. Pas d'integration continue du SDK `mcp`

- Le serveur suit le protocole MCP mais n'utilise pas de tests officiels du SDK.
- Les tests d'integration utilisent un client FastMCP en memoire (`fastmcp.Client`),
  pas un serveur reel.

## 10. Dependances

Le serveur depend de :
- API Produit externe (Docker compose cote equipe)
- API interne Backoffice (Bloc 1)
- Aucune autre source

Si l'un de ces services tombe, les outils concernes renvoient une erreur
claire via `ToolError` avec un code normalise (`upstream_unavailable`,
`not_found`, etc.). Pas de retry infini, pas de fallback magique.