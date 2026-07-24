"""Logique d'authentification, isolée des routes Flask.

Même principe que app/stock/service.py : la logique métier vit ici,
la route se contente de parser la requête et d'afficher le résultat.
"""

from flask_login import login_user, logout_user

from app.models import User


def attempt_login(email, plain_password):
    """Tente une connexion.

    Retourne (True, user) si succès, (False, message_erreur) sinon.

    Rejette explicitement :
    - un email inconnu
    - un mot de passe incorrect
    - un user soft-deleted (is_active = False)

    Le même message est renvoyé pour "email inconnu" et "mot de passe
    incorrect", pour ne pas révéler si un compte existe.
    """
    user = User.query.filter_by(email=email).first()

    if user is None or not user.check_password(plain_password):
        return False, "Email ou mot de passe incorrect."

    if not user.is_active:
        return False, "Ce compte a été désactivé."

    login_user(user)
    return True, user


def logout():
    logout_user()
