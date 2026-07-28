"""Fiche produit : disponibilité cross-branches (informatif, ajouté hors
MVP initial). Le common user ne peut transférer que depuis sa propre
branche (app/stock/service.py::transfer_stock) — cet écran ne fait que
l'informer d'où le produit est disponible ailleurs, aucune action.
"""

from app.models import Stock


def test_shows_other_branches_availability(
    client, login, common_user_lyon, branch_lyon, branch_paris, db
):
    db.session.add(Stock(branch_id=branch_paris.id, product_id=1, quantity=7))
    db.session.commit()

    login("lyon@test.local", "lyonpass")
    resp = client.get("/stock/product/1")

    assert resp.status_code == 200
    assert "Branche Paris".encode() in resp.data
    assert "7 en stock".encode() in resp.data


def test_shows_rupture_for_branch_with_no_stock(
    client, login, common_user_lyon, branch_paris
):
    login("lyon@test.local", "lyonpass")
    resp = client.get("/stock/product/1")

    assert resp.status_code == 200
    assert "Rupture".encode() in resp.data
