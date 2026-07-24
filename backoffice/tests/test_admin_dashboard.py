"""Dashboard admin (vue d'ensemble cross-branches, lecture seule) :
- accessible à l'admin, pas au common user (même règle que le reste
  de l'espace /admin, cf. test_critical_scenarios.py)
- les stats reflètent bien le stock réel des branches
- une ligne sous le seuil de stock faible apparaît dans les alertes
"""

from app.models import Stock


def test_common_user_blocked_from_dashboard(
    client, login, common_user_lyon
):
    login("lyon@test.local", "lyonpass")

    resp = client.get("/admin/dashboard")

    assert resp.status_code == 403


def test_admin_sees_dashboard_with_branch_stats(
    client, login, admin_user, db, branch_lyon, branch_paris
):
    db.session.add_all(
        [
            Stock(branch_id=branch_lyon.id, product_id=1, quantity=2),
            Stock(branch_id=branch_lyon.id, product_id=2, quantity=50),
            Stock(branch_id=branch_paris.id, product_id=1, quantity=10),
        ]
    )
    db.session.commit()

    login("admin@test.local", "adminpass")
    resp = client.get("/admin/dashboard")

    assert resp.status_code == 200
    # Lyon : 2 produits référencés, 52 unités, 1 sous le seuil (2 <= 5)
    assert "Branche Lyon".encode() in resp.data
    assert "Branche Paris".encode() in resp.data
    assert "2 restant(s)".encode() in resp.data


def test_dashboard_shows_no_alert_when_above_threshold(
    client, login, admin_user, db, branch_lyon
):
    db.session.add(
        Stock(branch_id=branch_lyon.id, product_id=1, quantity=100)
    )
    db.session.commit()

    login("admin@test.local", "adminpass")
    resp = client.get("/admin/dashboard")

    assert resp.status_code == 200
    assert "Aucune alerte".encode() in resp.data
