"""
Automated unit & integration test suite for Enterprise Subtasks & Acceptance Checklist System.
"""
import pytest
from models import db, Task, Subtask

def test_subtask_lifecycle(auth_user):
    """Test full CRUD lifecycle of subtasks under a deliverable."""
    client = auth_user["client"]

    # 1. Create a task
    t_res = client.post("/api/tasks", json={
        "title": "OAuth 2.0 PKCE Verification",
        "category": "Backend",
        "priority": "High"
    })
    assert t_res.status_code == 201
    task_id = t_res.get_json()["task"]["id"]

    # 2. Initially empty subtasks
    list_res = client.get(f"/api/tasks/{task_id}/subtasks")
    assert list_res.status_code == 200
    data = list_res.get_json()
    assert data["total"] == 0
    assert data["completed"] == 0
    assert data["progress_pct"] == 0
    assert data["subtasks"] == []

    # 3. Create Subtask 1
    s1_res = client.post(f"/api/tasks/{task_id}/subtasks", json={
        "title": "Define code_verifier and code_challenge generation"
    })
    assert s1_res.status_code == 201
    s1 = s1_res.get_json()["subtask"]
    assert s1["title"] == "Define code_verifier and code_challenge generation"
    assert s1["is_completed"] is False
    assert s1["completed_at"] is None
    s1_id = s1["id"]

    # 4. Create Subtask 2
    s2_res = client.post(f"/api/tasks/{task_id}/subtasks", json={
        "title": "Implement SHA-256 challenge validation decorator"
    })
    assert s2_res.status_code == 201
    s2_id = s2_res.get_json()["subtask"]["id"]

    # Verify task progress metrics: 0/2 (0%)
    list_res = client.get(f"/api/tasks/{task_id}/subtasks")
    assert list_res.get_json()["total"] == 2
    assert list_res.get_json()["completed"] == 0
    assert list_res.get_json()["progress_pct"] == 0

    # 5. Toggle Subtask 1 to completed
    toggle_res = client.patch(f"/api/subtasks/{s1_id}/toggle")
    assert toggle_res.status_code == 200
    t_data = toggle_res.get_json()
    assert t_data["subtask"]["is_completed"] is True
    assert t_data["subtask"]["completed_at"] is not None
    assert t_data["task_progress"]["completed"] == 1
    assert t_data["task_progress"]["progress_pct"] == 50

    # Verify nested toggle route also works
    toggle_nested_res = client.patch(f"/api/tasks/{task_id}/subtasks/{s2_id}/toggle")
    assert toggle_nested_res.status_code == 200
    assert toggle_nested_res.get_json()["subtask"]["is_completed"] is True
    assert toggle_nested_res.get_json()["task_progress"]["completed"] == 2
    assert toggle_nested_res.get_json()["task_progress"]["progress_pct"] == 100

    # Toggle back to incomplete
    toggle_back = client.patch(f"/api/subtasks/{s2_id}/toggle")
    assert toggle_back.status_code == 200
    assert toggle_back.get_json()["subtask"]["is_completed"] is False
    assert toggle_back.get_json()["subtask"]["completed_at"] is None
    assert toggle_back.get_json()["task_progress"]["completed"] == 1
    assert toggle_back.get_json()["task_progress"]["progress_pct"] == 50

    # 6. Update subtask title
    up_res = client.put(f"/api/subtasks/{s1_id}", json={
        "title": "Updated: Standardized PKCE code challenge generation"
    })
    assert up_res.status_code == 200
    assert up_res.get_json()["subtask"]["title"] == "Updated: Standardized PKCE code challenge generation"

    # 7. Delete Subtask 2
    del_res = client.delete(f"/api/subtasks/{s2_id}")
    assert del_res.status_code == 200

    # Remaining is 1 subtask, 1 completed (100%)
    list_res = client.get(f"/api/tasks/{task_id}/subtasks")
    assert list_res.get_json()["total"] == 1
    assert list_res.get_json()["completed"] == 1
    assert list_res.get_json()["progress_pct"] == 100


def test_subtask_validation(auth_user):
    """Test validation guards for empty title and non-existent IDs."""
    client = auth_user["client"]

    t_res = client.post("/api/tasks", json={"title": "Data Pipeline Cleanup"})
    task_id = t_res.get_json()["task"]["id"]

    # Missing title
    res = client.post(f"/api/tasks/{task_id}/subtasks", json={})
    assert res.status_code == 400
    assert "required" in res.get_json()["error"]

    # Whitespace title
    res = client.post(f"/api/tasks/{task_id}/subtasks", json={"title": "   "})
    assert res.status_code == 400
    assert "required" in res.get_json()["error"]

    # Non-existent task
    res = client.post("/api/tasks/99999/subtasks", json={"title": "Valid title"})
    assert res.status_code == 404

    # Non-existent subtask toggle
    res = client.patch("/api/subtasks/99999/toggle")
    assert res.status_code == 404

    # Update with empty title
    s_res = client.post(f"/api/tasks/{task_id}/subtasks", json={"title": "Initial"})
    subtask_id = s_res.get_json()["subtask"]["id"]
    res = client.put(f"/api/subtasks/{subtask_id}", json={"title": "  "})
    assert res.status_code == 400


def test_batch_create_subtasks(auth_user):
    """Test bulk subtask creation."""
    client = auth_user["client"]

    t_res = client.post("/api/tasks", json={"title": "Refactor Logging Infrastructure"})
    task_id = t_res.get_json()["task"]["id"]

    batch_payload = {
        "subtasks": [
            "Configure JSON log formatter",
            "Add request_id correlation context",
            "Stream error alerts to notification dispatcher"
        ]
    }
    res = client.post(f"/api/tasks/{task_id}/subtasks/batch", json=batch_payload)
    assert res.status_code == 201
    data = res.get_json()
    assert data["created_count"] == 3
    assert data["task_progress"]["total"] == 3
    assert data["task_progress"]["completed"] == 0

    # Malformed batch payload
    res = client.post(f"/api/tasks/{task_id}/subtasks/batch", json={"subtasks": []})
    assert res.status_code == 400


def test_ai_generate_subtasks(auth_user):
    """Test automated architectural milestone decomposition."""
    client = auth_user["client"]

    t_res = client.post("/api/tasks", json={
        "title": "Migrate Database Composite Indexes",
        "category": "Database"
    })
    task_id = t_res.get_json()["task"]["id"]

    res = client.post(f"/api/tasks/{task_id}/subtasks/ai-generate")
    assert res.status_code == 201
    data = res.get_json()
    assert len(data["subtasks"]) == 5
    assert data["task_progress"]["total"] == 5

    # Verify database category templates were applied
    titles = [s["title"] for s in data["subtasks"]]
    assert any("Schema" in t or "Migration" in t or "Query" in t for t in titles)


def test_task_to_dict_includes_subtasks(auth_user):
    """Verify that Task.to_dict() dynamically includes subtasks metadata and progress."""
    client = auth_user["client"]

    t_res = client.post("/api/tasks", json={"title": "Payment Gateway Sandbox"})
    task_id = t_res.get_json()["task"]["id"]

    # Add 2 subtasks
    s1_res = client.post(f"/api/tasks/{task_id}/subtasks", json={"title": "Stripe webhook secret validation"})
    s1_id = s1_res.get_json()["subtask"]["id"]
    client.post(f"/api/tasks/{task_id}/subtasks", json={"title": "Idempotency key duplicate check"})

    # Complete 1 subtask
    client.patch(f"/api/subtasks/{s1_id}/toggle")

    # Fetch task via GET /api/tasks/<id>
    get_res = client.get(f"/api/tasks/{task_id}")
    assert get_res.status_code == 200
    task_dict = get_res.get_json()["task"]

    assert task_dict["subtasks_count"] == 2
    assert task_dict["subtasks_completed_count"] == 1
    assert task_dict["subtask_progress_pct"] == 50
    assert len(task_dict["subtasks"]) == 2


def test_cascade_delete_subtasks(auth_user, app):
    """Test that deleting a parent task cascades and cleanly deletes all subtasks."""
    client = auth_user["client"]

    t_res = client.post("/api/tasks", json={"title": "Temporary Deprecated Microservice"})
    task_id = t_res.get_json()["task"]["id"]

    s_res = client.post(f"/api/tasks/{task_id}/subtasks", json={"title": "Decommission pods"})
    subtask_id = s_res.get_json()["subtask"]["id"]

    with app.app_context():
        assert db.session.get(Subtask, subtask_id) is not None

    # Delete parent task
    del_res = client.delete(f"/api/tasks/{task_id}")
    assert del_res.status_code == 200

    with app.app_context():
        assert db.session.get(Subtask, subtask_id) is None


def test_cross_team_subtask_isolation(app, auth_user, second_user):
    """Test that cross-squad data isolation prevents unauthorized users from modifying subtasks."""
    admin_client = auth_user["client"]
    second_client = second_user["client"]

    # Create Team 1 and Team 2
    with app.app_context():
        from models import Team, User
        t1 = Team(name="Security Squad")
        t2 = Team(name="Mobile Squad")
        db.session.add_all([t1, t2])
        db.session.commit()

        # Put second user into Team 2
        u2 = db.session.get(User, second_user["user"]["id"])
        u2.team_id = t2.id
        u2.role = "Member"
        u2.is_admin = False

        # Put admin user into Team 1
        u1 = db.session.get(User, auth_user["user"]["id"])
        u1.team_id = t1.id
        db.session.commit()
        t1_id = t1.id

    # Create task scoped to Team 1
    t_res = admin_client.post("/api/tasks", json={
        "title": "Audit SSL Cipher Suites",
        "team_id": t1_id
    })
    assert t_res.status_code == 201
    task_id = t_res.get_json()["task"]["id"]

    # Admin adds a subtask
    s_res = admin_client.post(f"/api/tasks/{task_id}/subtasks", json={"title": "Disable TLS 1.0/1.1"})
    assert s_res.status_code == 201
    subtask_id = s_res.get_json()["subtask"]["id"]

    # Member of Team 2 tries to list subtasks of Team 1's task -> 403 Forbidden
    res = second_client.get(f"/api/tasks/{task_id}/subtasks")
    assert res.status_code == 403

    # Member of Team 2 tries to add subtask -> 403 Forbidden
    res = second_client.post(f"/api/tasks/{task_id}/subtasks", json={"title": "Unauthorized addition"})
    assert res.status_code == 403

    # Member of Team 2 tries to toggle subtask -> 403 Forbidden
    res = second_client.patch(f"/api/subtasks/{subtask_id}/toggle")
    assert res.status_code == 403

    # Member of Team 2 tries to delete subtask -> 403 Forbidden
    res = second_client.delete(f"/api/subtasks/{subtask_id}")
    assert res.status_code == 403
