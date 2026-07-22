"""
Authentification - Pôle A.

Choix : bcrypt pour le hachage, sessions Flask-Login pour l'auth.

Pourquoi bcrypt et pas SHA256 ?
- SHA256 est un hash *rapide*, conçu pour vérifier l'intégrité de fichiers,
  pas pour protéger des secrets. Rapide = facile à bruteforcer avec du
  matériel dédié (GPU/ASIC), on peut tester des milliards de mots de passe/s.
- bcrypt est volontairement lent (cost factor réglable) et incorpore un sel
  aléatoire à chaque hachage : deux utilisateurs avec le même mot de passe
  auront deux hash différents, et l'attaque par rainbow table est inutile.

Pourquoi des sessions plutôt qu'un JWT ?
- Le Backoffice est une appli web classique (pas une API consommée par un
  client externe/mobile). Flask-Login gère le cookie de session côté
  serveur, avec révocation immédiate possible (soft-delete, logout).
"""

import bcrypt
from flask_login import LoginManager, login_user, logout_user

from models import User

login_manager = LoginManager()
login_manager.login_view = "login"  # nom de la route de login, à adapter


def init_auth(app):
    login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def hash_password(plain_password: str) -> str:
    """Hache un mot de passe en clair avec bcrypt. À utiliser à la création
    d'un user et au changement de mot de passe."""
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Vérifie un mot de passe en clair contre son hash stocké."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), password_hash.encode("utf-8")
    )


def attempt_login(username: str, plain_password: str):
    """
    Tente une connexion.

    Retourne (True, user) si succès, (False, message_erreur) sinon.

    Rejette explicitement :
    - un username inconnu
    - un mot de passe incorrect
    - un user soft-deleted (is_active = False)
    """
    user = User.query.filter_by(username=username).first()

    if user is None:
        return False, "Identifiants invalides."

    if not user.is_active:
        return False, "Ce compte a été désactivé."

    if not verify_password(plain_password, user.password_hash):
        return False, "Identifiants invalides."

    login_user(user)
    return True, user


def logout():
    logout_user()
