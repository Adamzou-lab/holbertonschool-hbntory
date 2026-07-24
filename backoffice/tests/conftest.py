import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db as _db
from app.models import ROLE_ADMIN, ROLE_COMMON, Branch, User


@pytest.fixture
def app():
    application = create_app(TestConfig)
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    return _db


@pytest.fixture
def login(client):
    def _login(email, password):
        return client.post(
            "/login", data={"email": email, "password": password}
        )

    return _login


@pytest.fixture
def branch_lyon(db):
    branch = Branch(name="Branche Lyon")
    db.session.add(branch)
    db.session.commit()
    return branch


@pytest.fixture
def branch_paris(db):
    branch = Branch(name="Branche Paris")
    db.session.add(branch)
    db.session.commit()
    return branch


@pytest.fixture
def admin_user(db):
    user = User(
        email="admin@test.local", username="Admin", role=ROLE_ADMIN,
        is_active=True,
    )
    user.set_password("adminpass")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def common_user_lyon(db, branch_lyon):
    user = User(
        email="lyon@test.local", username="Lyon", role=ROLE_COMMON,
        branch_id=branch_lyon.id, is_active=True,
    )
    user.set_password("lyonpass")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def common_user_paris(db, branch_paris):
    user = User(
        email="paris@test.local", username="Paris", role=ROLE_COMMON,
        branch_id=branch_paris.id, is_active=True,
    )
    user.set_password("parispass")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def deactivated_user(db, branch_lyon):
    user = User(
        email="gone@test.local", username="Gone", role=ROLE_COMMON,
        branch_id=branch_lyon.id, is_active=False,
    )
    user.set_password("goneaway")
    db.session.add(user)
    db.session.commit()
    return user
