import pytest

def test_admin_stats(auth_user):
    """Admin user can access system-wide statistics."""
    client = auth_user["client"]
    res = client.get("/api/admin/stats")
    assert res.status_code == 200
    data = res.get_json()
    assert "total_users" in data
    assert "total_tasks" in data
    assert "completion_rate" in data

def test_admin_users_list(auth_user, second_user):
    """Admin user can list all registered users with task metrics."""
    client = auth_user["client"]
    res = client.get("/api/admin/users")
    assert res.status_code == 200
    users = res.get_json()["users"]
    assert len(users) >= 2
    emails = [u["email"] for u in users]
    assert auth_user["user"]["email"] in emails
    assert second_user["user"]["email"] in emails

def test_non_admin_forbidden(second_user):
    """Regular user cannot access admin endpoints (403 Forbidden)."""
    client = second_user["client"]
    assert client.get("/api/admin/stats").status_code == 403
    assert client.get("/api/admin/users").status_code == 403
    assert client.post("/api/admin/users/1/toggle-admin").status_code == 403

def test_toggle_admin_role(auth_user, second_user):
    """Admin can promote a regular user to admin and demote back."""
    admin_client = auth_user["client"]
    target_id = second_user["user"]["id"]

    # Promote to admin
    promote_res = admin_client.post(f"/api/admin/users/{target_id}/toggle-admin")
    assert promote_res.status_code == 200
    assert promote_res.get_json()["user"]["is_admin"] is True

    # Now second_user should be able to access admin stats
    assert second_user["client"].get("/api/admin/stats").status_code == 200

    # Demote back
    demote_res = admin_client.post(f"/api/admin/users/{target_id}/toggle-admin")
    assert demote_res.status_code == 200
    assert demote_res.get_json()["user"]["is_admin"] is False

def test_prevent_self_demotion(auth_user):
    """Admin cannot remove admin rights from their own account."""
    client = auth_user["client"]
    my_id = auth_user["user"]["id"]
    res = client.post(f"/api/admin/users/{my_id}/toggle-admin")
    assert res.status_code == 400
    assert "Cannot remove admin status from your own" in res.get_json()["error"]

def test_admin_role_update_rejects_invalid_team_id(auth_user, second_user):
    client = auth_user["client"]
    target_id = second_user["user"]["id"]

    invalid_id = client.post(f"/api/admin/users/{target_id}/role", json={"team_id": "not-an-id"})
    assert invalid_id.status_code == 400
    assert invalid_id.get_json()["error"] == "Team ID must be a positive integer."

    missing_team = client.post(f"/api/admin/users/{target_id}/role", json={"team_id": 999999})
    assert missing_team.status_code == 404
    assert missing_team.get_json()["error"] == "Team not found."

def test_admin_delete_user(auth_user, second_user):
    """Admin can delete another user and their tasks."""
    admin_client = auth_user["client"]
    target_id = second_user["user"]["id"]

    del_res = admin_client.delete(f"/api/admin/users/{target_id}")
    assert del_res.status_code == 200

    # Verify user is gone
    users = admin_client.get("/api/admin/users").get_json()["users"]
    assert all(u["id"] != target_id for u in users)

def test_prevent_self_deletion(auth_user):
    """Admin cannot delete their own account via admin endpoint."""
    client = auth_user["client"]
    my_id = auth_user["user"]["id"]
    res = client.delete(f"/api/admin/users/{my_id}")
    assert res.status_code == 400
    assert "Cannot delete your own active admin account" in res.get_json()["error"]
