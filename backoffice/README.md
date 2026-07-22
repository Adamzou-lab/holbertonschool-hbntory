# Backoffice — StockFlow

Flask + SQLAlchemy + Flask-Migrate + Flask-Login (SSR Jinja2, cf. [docs/decisions.md](../docs/decisions.md)).

## Lancer en local

```bash
cd backoffice
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

export FLASK_APP=wsgi.py
.venv/bin/flask db upgrade      # crée la base (SQLite par défaut, cf. app/config.py)

# ADMIN_PASSWORD à définir explicitement en dehors d'un contexte de dev
ADMIN_EMAIL=admin@stockflow.local ADMIN_PASSWORD=changeme123 .venv/bin/flask seed

.venv/bin/flask run
```

Compte admin créé par `flask seed` (le seul admin du système, cf. règle du sujet). Le seed crée
aussi 3 branches de démo (Lyon, Paris, Marseille) pour pouvoir créer des common users et tester.

## Périmètre actuel (MVP priorité 1, cf. [docs/mvp.md](../docs/mvp.md))

- Auth (Flask-Login, mots de passe hashés via `werkzeug.security`), un seul admin.
- Admin : lister/créer/modifier les common users, assigner une branche, soft-delete
  (désactivation), changer le mot de passe.
- Common user : consulter/ajouter/retirer le stock de sa branche uniquement (`product_id` +
  `quantity`), quantité jamais négative.
- Vérification des rôles côté backend (`app/decorators.py::role_required`), jamais seulement
  côté template.

**Volontairement absent pour l'instant** (cf. `docs/mvp.md` priorité 3 / hors-scope) : noms/
descriptions produit (viendront de l'API Produit externe, pas stockés ici), transferts
inter-branches, règles de notification, prévisions, import/export CSV, recherche par image. Le
mockup exploratoire qui a servi de base visuelle est conservé dans
[docs/mockups/stock-dashboard.html](../docs/mockups/stock-dashboard.html).

## Authentification et autorisation

**Hashing des mots de passe : `werkzeug.security` (`generate_password_hash` /
`check_password_hash`).**

- Par défaut, Werkzeug utilise `scrypt` (ou `pbkdf2:sha256` selon la version installée) — deux
  fonctions de dérivation de clé conçues spécifiquement pour le stockage de mots de passe : elles
  sont volontairement lentes et paramétrables (coût réglable), et incorporent un sel aléatoire
  généré à chaque hachage.
- **Pourquoi pas un hash générique comme SHA256 seul ?** SHA256 est conçu pour vérifier
  l'intégrité de données (rapide à calculer), pas pour protéger des secrets. Sa rapidité est
  justement ce qui le rend inadapté aux mots de passe : un attaquant disposant du hash peut tester
  des milliards de mots de passe par seconde sur du matériel dédié (GPU/ASIC). `scrypt`/`pbkdf2`
  sont délibérément coûteux en calcul pour rendre cette attaque impraticable, et le sel empêche
  les attaques par rainbow table (même mot de passe → hash différent pour deux comptes).
- **Vérification** : `User.check_password()` appelle `check_password_hash(self.password_hash,
  raw_password)`, qui recalcule le hash avec le même sel stocké dans `password_hash` et compare
  en temps constant.

**Session** : Flask-Login (cookie de session côté serveur), pas de JWT — le Backoffice est une
appli web classique consommée par un navigateur, pas une API tierce. Un `logout()` ou un
soft-delete (`is_active=False`) invalide immédiatement l'accès (Flask-Login refuse la connexion
d'un `User` dont `is_active` est `False`, cf. `login_manager.user_loader` dans `app/__init__.py`
et l'attribut `is_active` du modèle qui masque celui par défaut de `UserMixin`).

**Autorisation par rôle** : `app/decorators.py::role_required(role)`, appliqué à chaque route
sensible (jamais seulement une question d'affichage côté template). Un common user n'agit que sur
sa propre branche parce que les routes stock utilisent toujours `current_user.branch_id` — jamais
un `branch_id` fourni par le client. `same_branch_required` existe en plus pour toute future route
qui accepterait un `branch_id` externe (défense en profondeur).
