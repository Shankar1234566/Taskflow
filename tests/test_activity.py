import pytest

def test_activity_logging_on_task_actions(auth_user):
    """Task operations automatically record audit trail entries in ActivityLog."""
    client = auth_user["client"]

    # 1. Create a task
    create_res = client.post("/api/tasks", json={
        "title": "Audit Trail Task",
        "priority": "Critical",
        "tags": "security,audit"
    })
    task_id = create_res.get_json()["task"]["id"]

    # 2. Update task
    client.put(f"/api/tasks/{task_id}", json={"title": "Audit Trail Task - Updated"})

    # 3. Star task
    client.post(f"/api/tasks/{task_id}/star")

    # 4. Complete task
    client.patch(f"/api/tasks/{task_id}/complete")

    # 5. Fetch activities
    act_res = client.get("/api/activity")
    assert act_res.status_code == 200
    activities = act_res.get_json()["activities"]
    assert len(activities) >= 4

    actions = [a["action"] for a in activities]
    assert "created" in actions
    assert "updated" in actions
    assert "starred" in actions
    assert "completed" in actions

def test_clear_activity_history(auth_user):
    """User can clear their own activity logs."""
    client = auth_user["client"]
    client.post("/api/tasks", json={"title": "Temporary Task"})

    # Clear logs
    del_res = client.delete("/api/activity")
    assert del_res.status_code == 200

    # Ensure activity list is now empty
    act_res = client.get("/api/activity")
    assert len(act_res.get_json()["activities"]) == 0
