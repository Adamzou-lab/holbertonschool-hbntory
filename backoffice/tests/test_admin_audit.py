"""Journal des actions admin (app/admin/audit.py) : création, modification
et (dés)activation d'un compte common user laissent une trace consultable
sur /admin/audit — traçabilité pure, jamais utilisée pour restreindre quoi
que ce soit (contrairement à role_required)."""

from app.models import AdminAction


def test_creating_user_logs_action(
    client, login, admin_user, branch_lyon
):
    login("admin@test.local", "adminpass")
    client.post(
        "/admin/users/new",
        data={
            "email": "new@test.local",
            "username": "New",
            "password": "newpass123",
            "branch_id": str(branch_lyon.id),
        },
    )

    action = AdminAction.query.filter_by(action_type="user_created").first()
    assert action is not None
    assert action.actor_id == admin_user.id


def test_deactivating_user_logs_action(
    client, login, admin_user, common_user_lyon
):
    login("admin@test.local", "adminpass")
    client.post(f"/admin/users/{common_user_lyon.id}/toggle-active")

    action = AdminAction.query.filter_by(
        action_type="user_deactivated"
    ).first()
    assert action is not None
    assert action.target_user_id == common_user_lyon.id


def test_common_user_blocked_from_audit_log(client, login, common_user_lyon):
    login("lyon@test.local", "lyonpass")

    resp = client.get("/admin/audit")

    assert resp.status_code == 403


def test_admin_sees_audit_log(
    client, login, admin_user, common_user_lyon
):
    login("admin@test.local", "adminpass")
    client.post(f"/admin/users/{common_user_lyon.id}/toggle-active")

    resp = client.get("/admin/audit")

    assert resp.status_code == 200
    assert "Compte désactivé".encode() in resp.data
    assert "Admin".encode() in resp.data
