"""Scénarios critiques explicitement demandés par le sujet (Task 7) :
retrait > stock refusé, cross-branche refusé, user désactivé ne peut
pas se connecter, admin ne gère pas le stock — plus quelques scénarios
voisins (rôles inversés, API interne) qui protègent les mêmes limites.
"""

from unittest.mock import Mock, patch

from app.models import Stock


def test_deactivated_user_cannot_login(client, login, deactivated_user):
    resp = login("gone@test.local", "goneaway")

    assert resp.status_code == 200
    assert "désactivé".encode() in resp.data

    stock_resp = client.get("/stock")
    assert stock_resp.status_code == 302
    assert "/login" in stock_resp.headers["Location"]


def test_wrong_password_rejected(client, login, common_user_lyon):
    resp = login("lyon@test.local", "wrong-password")

    assert resp.status_code == 200
    assert "incorrect".encode() in resp.data


def test_remove_more_than_available_refused(
    client, login, common_user_lyon, branch_lyon
):
    login("lyon@test.local", "lyonpass")
    client.post("/stock/add", data={"product_id": "1", "quantity": "5"})

    resp = client.post(
        "/stock/remove",
        data={"product_id": "1", "quantity": "10"},
        follow_redirects=True,
    )

    stock = Stock.query.filter_by(
        branch_id=branch_lyon.id, product_id=1
    ).first()
    assert stock.quantity == 5
    assert "insuffisant".encode() in resp.data


def test_add_zero_quantity_rejected(client, login, common_user_lyon):
    login("lyon@test.local", "lyonpass")

    client.post("/stock/add", data={"product_id": "1", "quantity": "0"})

    assert Stock.query.filter_by(product_id=1).first() is None


def test_common_user_cannot_smuggle_another_branch_id(
    client, login, common_user_lyon, branch_lyon, branch_paris
):
    """Les routes stock ne lisent jamais de branch_id envoyé par le
    client — même en en glissant un dans le formulaire, l'opération
    reste bornée à current_user.branch_id (Lyon)."""
    login("lyon@test.local", "lyonpass")

    client.post(
        "/stock/add",
        data={
            "product_id": "1",
            "quantity": "5",
            "branch_id": str(branch_paris.id),
        },
    )

    lyon_stock = Stock.query.filter_by(
        branch_id=branch_lyon.id, product_id=1
    ).first()
    paris_stock = Stock.query.filter_by(
        branch_id=branch_paris.id, product_id=1
    ).first()
    assert lyon_stock.quantity == 5
    assert paris_stock is None


def test_common_user_cannot_see_another_branch_stock(
    client, login, common_user_lyon, common_user_paris, branch_paris, db
):
    login("paris@test.local", "parispass")
    client.post("/stock/add", data={"product_id": "9", "quantity": "3"})
    client.post("/logout")

    login("lyon@test.local", "lyonpass")
    resp = client.get("/stock")

    assert b"Produit #9" not in resp.data
    paris_stock = Stock.query.filter_by(
        branch_id=branch_paris.id, product_id=9
    ).first()
    assert paris_stock.quantity == 3


def test_admin_cannot_access_stock_routes(client, login, admin_user):
    login("admin@test.local", "adminpass")

    resp = client.get("/stock")

    assert resp.status_code == 403


def test_common_user_cannot_access_admin_routes(
    client, login, common_user_lyon
):
    login("lyon@test.local", "lyonpass")

    resp = client.get("/admin/users")

    assert resp.status_code == 403


def test_internal_api_rejects_missing_token(client):
    resp = client.get("/api/internal/branches")
    assert resp.status_code == 403


def test_internal_api_rejects_wrong_token(client):
    resp = client.get(
        "/api/internal/branches",
        headers={"X-Internal-Token": "not-the-right-token"},
    )
    assert resp.status_code == 403


def test_internal_api_accepts_valid_token(client, app, branch_lyon):
    resp = client.get(
        "/api/internal/branches",
        headers={
            "X-Internal-Token": app.config["BACKOFFICE_INTERNAL_TOKEN"]
        },
    )
    assert resp.status_code == 200


def test_happy_path_login_add_view(client, login, common_user_lyon):
    login("lyon@test.local", "lyonpass")

    add_resp = client.post(
        "/stock/add",
        data={"product_id": "1", "quantity": "10"},
        follow_redirects=True,
    )
    assert add_resp.status_code == 200

    stock_page = client.get("/stock")
    assert b"Produit #1" in stock_page.data
    assert b"10" in stock_page.data


def test_add_stock_rejected_for_unknown_product(
    client, login, common_user_lyon
):
    """product_exists() renvoie False quand l'API répond clairement
    "pas trouvé" (404) — dans ce cas add_stock refuse. Toujours 127.0.0.1:1
    (injoignable) dans TestConfig d'habitude, donc ce cas précis (API qui
    répond mais dit non) doit être simulé explicitement.
    """
    login("lyon@test.local", "lyonpass")

    fake_response = Mock(status_code=404)
    with patch(
        "app.products.client.requests.get", return_value=fake_response
    ):
        resp = client.post(
            "/stock/add",
            data={"product_id": "999", "quantity": "5"},
            follow_redirects=True,
        )

    assert resp.status_code == 200
    # Jinja échappe l'apostrophe (n&#39;existe) — on cherche sans elle.
    assert "existe pas dans le catalogue".encode() in resp.data
    assert Stock.query.filter_by(product_id=999).first() is None


def test_add_stock_allowed_when_products_api_unreachable(
    client, login, common_user_lyon
):
    """Quand l'API Produit est injoignable (product_exists() -> None), on
    ne bloque pas l'opération de stock à cause d'une dépendance externe en
    panne — c'est le comportement par défaut de TestConfig
    (PRODUCTS_API_BASE_URL pointe vers un port injoignable), donc ce test
    documente juste explicitement ce choix.
    """
    login("lyon@test.local", "lyonpass")

    resp = client.post(
        "/stock/add",
        data={"product_id": "42", "quantity": "3"},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    row = Stock.query.filter_by(product_id=42).first()
    assert row is not None
    assert row.quantity == 3
