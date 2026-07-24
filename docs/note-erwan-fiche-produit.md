# Pourquoi la fiche produit reste en lecture seule

Erwan, petite note suite à une idée qu'on avait eue (un bouton crayon pour éditer nom/poids/taille
sur la fiche produit du Backoffice) — on a fait marche arrière, voici pourquoi.

## Deux raisons, indépendantes l'une de l'autre

**1. L'API Produit externe est en lecture seule, par contrat.**
Son propre README le dit explicitement : *"This service simulates a supplier catalog... you are
not expected to modify this service."* Elle n'expose que des routes `GET`
(`/api/v1/products`, `/api/v1/products/{id}`, etc.) — aucune route d'écriture. Techniquement, on
ne peut pas modifier le catalogue même si on voulait, quel que soit ce qu'on construit côté
Backoffice.

**2. Notre propre règle d'or l'interdit aussi, indépendamment du point 1.**
`docs/mvp.md`, section "Hors scope" (posée dès le Task 0, donc avant même de connaître le détail
de l'API) : *"Stockage de toute donnée produit (nom, prix, description, image) en base locale."*
Si on avait stocké un poids/une taille dans notre DB pour "compléter" la fiche produit, ça aurait
violé cette règle — que l'API soit modifiable ou non.

## Ce qui reste possible

La fiche produit (`/stock/product/<id>`) continue d'afficher tout ce que l'API Produit renvoie en
direct (nom, description, prix, catégorie, marque, fournisseur, tags — y compris `weight_kg` si on
veut l'ajouter à l'affichage, ça ne coûte rien puisque c'est juste de la lecture). Ce qui n'est pas
possible, c'est de permettre à un common user de modifier ces valeurs depuis le Backoffice.

Si un jour il faut vraiment un poids/une taille éditables (ex: pour calculer un espace de stockage
par branche), il faudrait le faire comme un attribut explicitement **local au Backoffice**, associé
au `product_id` mais clairement pas confondu avec "modifier le produit" — et probablement à valider
avec le prof avant, vu que ça touche direct à une règle du sujet.
