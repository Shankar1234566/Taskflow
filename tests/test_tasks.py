from datetime import date, timedelta
import pytest

def test_create_task(auth_user):
    """Test successful task creation with all fields."""
    client = auth_user["client"]
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    payload = {
        "title": "Complete Flask integration",
        "description": "Write APIs and run tests",
        "category": "Development",
        "priority": "High",
        "due_date": tomorrow
    }
    res = client.post("/api/tasks", json=payload)
    assert res.status_code == 201
    data = res.get_json()
    assert "task" in data
    assert data["task"]["title"] == "Complete Flask integration"
    assert data["task"]["priority"] == "High"
    assert data["task"]["category"] == "Development"
    assert data["task"]["due_date"] == tomorrow
    assert data["task"]["completed"] is False
    assert data["task"]["status"] == "In Progress"

def test_task_input_validation(auth_user):
    """Test validation errors for empty title, invalid priority, and malformed date."""
    client = auth_user["client"]

    # Missing title
    res = client.post("/api/tasks", json={"priority": "High"})
    assert res.status_code == 400
    assert "Title is required" in res.get_json()["error"]

    # Empty string title
    res = client.post("/api/tasks", json={"title": "   "})
    assert res.status_code == 400
    assert "Title is required" in res.get_json()["error"]

    # Invalid priority
    res = client.post("/api/tasks", json={"title": "Test Task", "priority": "Urgent"})
    assert res.status_code == 400
    assert "Priority must be" in res.get_json()["error"]

    # Invalid date format
    res = client.post("/api/tasks", json={"title": "Test Task", "due_date": "not-a-date"})
    assert res.status_code == 400
    assert "Due date must be in YYYY-MM-DD" in res.get_json()["error"]

    # Invalid relationship IDs must be rejected instead of raising an exception.
    for field in ("team_id", "assigned_to_id"):
        res = client.post("/api/tasks", json={"title": "Invalid ID", field: "not-an-id"})
        assert res.status_code == 400
        assert "positive integer" in res.get_json()["error"]

    res = client.post("/api/tasks", json={"title": "Invalid Team", "team_id": 999999})
    assert res.status_code == 404
    assert res.get_json()["error"] == "Team not found."

def test_task_update_rejects_invalid_relationship_ids(auth_user):
    client = auth_user["client"]
    task = client.post("/api/tasks", json={"title": "Update relationship"}).get_json()["task"]

    invalid_id = client.put(f"/api/tasks/{task['id']}", json={"team_id": "not-an-id"})
    assert invalid_id.status_code == 400
    assert "positive integer" in invalid_id.get_json()["error"]

    missing_team = client.put(f"/api/tasks/{task['id']}", json={"team_id": 999999})
    assert missing_team.status_code == 404
    assert missing_team.get_json()["error"] == "Team not found."

def test_prevent_mass_assignment(auth_user, second_user):
    """Ensure user_id cannot be spoofed to assign tasks to someone else."""
    client = auth_user["client"]
    victim_id = second_user["user"]["id"]

    res = client.post("/api/tasks", json={
        "title": "Spoofed Task",
        "user_id": victim_id,
        "id": 99999
    })
    assert res.status_code == 201
    task = res.get_json()["task"]
    # Task must belong to the logged-in user, not victim_id
    assert task["user_id"] == auth_user["user"]["id"]
    assert task["user_id"] != victim_id

def test_read_tasks_and_pagination_or_filtering(auth_user):
    """Test reading tasks, searching by title/desc, and filtering by priority/category/status."""
    client = auth_user["client"]
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    next_week = (date.today() + timedelta(days=5)).isoformat()

    # Create several tasks
    client.post("/api/tasks", json={"title": "Write documentation", "category": "Work", "priority": "Low", "due_date": today})
    client.post("/api/tasks", json={"title": "Fix frontend bug", "description": "urgent fix needed", "category": "Development", "priority": "High", "due_date": next_week})
    client.post("/api/tasks", json={"title": "Overdue task", "category": "Personal", "priority": "Medium", "due_date": yesterday})

    # Read all tasks
    res = client.get("/api/tasks")
    assert res.status_code == 200
    tasks = res.get_json()["tasks"]
    assert len(tasks) == 3

    # Search filter
    search_res = client.get("/api/tasks?search=urgent")
    assert search_res.status_code == 200
    search_tasks = search_res.get_json()["tasks"]
    assert len(search_tasks) == 1
    assert search_tasks[0]["title"] == "Fix frontend bug"

    # Priority filter
    priority_res = client.get("/api/tasks?priority=High")
    assert priority_res.status_code == 200
    assert len(priority_res.get_json()["tasks"]) == 1

    # Category filter
    cat_res = client.get("/api/tasks?category=Work")
    assert cat_res.status_code == 200
    assert len(cat_res.get_json()["tasks"]) == 1

    # Overdue status filter
    overdue_res = client.get("/api/tasks?status=overdue")
    assert overdue_res.status_code == 200
    assert len(overdue_res.get_json()["tasks"]) == 1
    assert overdue_res.get_json()["tasks"][0]["title"] == "Overdue task"

def test_update_task(auth_user):
    """Test updating task title, priority, description, and due date."""
    client = auth_user["client"]
    created = client.post("/api/tasks", json={"title": "Initial Title", "priority": "Low"}).get_json()["task"]
    task_id = created["id"]

    update_res = client.put(f"/api/tasks/{task_id}", json={
        "title": "Updated Title",
        "priority": "High",
        "description": "Added detailed description"
    })
    assert update_res.status_code == 200
    updated_task = update_res.get_json()["task"]
    assert updated_task["title"] == "Updated Title"
    assert updated_task["priority"] == "High"
    assert updated_task["description"] == "Added detailed description"

def test_toggle_task_completion(auth_user):
    """Test toggling task completion status and setting explicit completion."""
    client = auth_user["client"]
    task = client.post("/api/tasks", json={"title": "Completion Test"}).get_json()["task"]
    task_id = task["id"]
    assert task["completed"] is False

    # Toggle to true
    res1 = client.patch(f"/api/tasks/{task_id}/complete")
    assert res1.status_code == 200
    assert res1.get_json()["task"]["completed"] is True
    assert res1.get_json()["task"]["status"] == "Completed"

    # Toggle to false
    res2 = client.patch(f"/api/tasks/{task_id}/complete")
    assert res2.status_code == 200
    assert res2.get_json()["task"]["completed"] is False

    # Explicit set to true
    res3 = client.patch(f"/api/tasks/{task_id}/complete", json={"completed": True})
    assert res3.status_code == 200
    assert res3.get_json()["task"]["completed"] is True

def test_delete_task(auth_user):
    """Test deleting a task."""
    client = auth_user["client"]
    task = client.post("/api/tasks", json={"title": "To be deleted"}).get_json()["task"]
    task_id = task["id"]

    del_res = client.delete(f"/api/tasks/{task_id}")
    assert del_res.status_code == 200

    # Ensure it no longer exists
    get_res = client.get(f"/api/tasks/{task_id}")
    assert get_res.status_code == 404

def test_cross_user_isolation(auth_user, second_user):
    """
    CRITICAL: Verify User B CANNOT read, update, complete, or delete User A's task.
    Returns 404 without revealing existence.
    """
    client_a = auth_user["client"]
    client_b = second_user["client"]

    # User A creates a task
    task_a = client_a.post("/api/tasks", json={
        "title": "User A Private Task",
        "description": "Secret stuff"
    }).get_json()["task"]
    task_a_id = task_a["id"]

    # User B attempts to read User A's task
    read_res = client_b.get(f"/api/tasks/{task_a_id}")
    assert read_res.status_code == 404
    assert read_res.get_json()["error"] == "Task not found."

    # User B list tasks should NOT include User A's task
    list_b = client_b.get("/api/tasks").get_json()["tasks"]
    assert all(t["id"] != task_a_id for t in list_b)

    # User B attempts to update User A's task
    update_res = client_b.put(f"/api/tasks/{task_a_id}", json={"title": "Hacked Title"})
    assert update_res.status_code == 404

    # User B attempts to toggle completion of User A's task
    complete_res = client_b.patch(f"/api/tasks/{task_a_id}/complete")
    assert complete_res.status_code == 404

    # User B attempts to delete User A's task
    delete_res = client_b.delete(f"/api/tasks/{task_a_id}")
    assert delete_res.status_code == 404

    # User A's task must remain completely intact
    intact_res = client_a.get(f"/api/tasks/{task_a_id}")
    assert intact_res.status_code == 200
    assert intact_res.get_json()["task"]["title"] == "User A Private Task"

def test_unauthenticated_task_access_rejected(client):
    """Unauthenticated client cannot access task endpoints."""
    assert client.get("/api/tasks").status_code == 401
    assert client.post("/api/tasks", json={"title": "No Auth"}).status_code == 401
    assert client.get("/api/tasks/1").status_code == 401
    assert client.put("/api/tasks/1", json={"title": "No Auth"}).status_code == 401
    assert client.patch("/api/tasks/1/complete").status_code == 401
    assert client.delete("/api/tasks/1").status_code == 401

def test_critical_priority_and_tags(auth_user):
    """Test Critical priority and tags parsing."""
    client = auth_user["client"]
    res = client.post("/api/tasks", json={
        "title": "System Outage Emergency",
        "priority": "Critical",
        "tags": "infra, devops, p0",
        "due_time": "18:00"
    })
    assert res.status_code == 201
    task = res.get_json()["task"]
    assert task["priority"] == "Critical"
    assert task["due_time"] == "18:00"
    assert "infra" in task["tags_list"]
    assert "devops" in task["tags_list"]

def test_toggle_star_and_filter(auth_user):
    """Test starring tasks and filtering by starred."""
    client = auth_user["client"]
    task = client.post("/api/tasks", json={"title": "Star Me"}).get_json()["task"]
    task_id = task["id"]
    assert task["is_starred"] is False

    # Toggle star to True
    res = client.post(f"/api/tasks/{task_id}/star")
    assert res.status_code == 200
    assert res.get_json()["task"]["is_starred"] is True

    # Filter by starred=true
    star_filter = client.get("/api/tasks?starred=true").get_json()["tasks"]
    assert len(star_filter) >= 1
    assert any(t["id"] == task_id for t in star_filter)

def test_duplicate_task(auth_user):
    """Test duplicating an existing task."""
    client = auth_user["client"]
    original = client.post("/api/tasks", json={
        "title": "Template Task",
        "priority": "High",
        "category": "Marketing",
        "tags": "campaign"
    }).get_json()["task"]

    dup_res = client.post(f"/api/tasks/{original['id']}/duplicate")
    assert dup_res.status_code == 201
    clone = dup_res.get_json()["task"]
    assert "Template Task (Copy)" in clone["title"]
    assert clone["priority"] == "High"
    assert clone["category"] == "Marketing"
    assert clone["id"] != original["id"]

def test_bulk_complete_and_delete(auth_user):
    """Test bulk complete and bulk delete endpoints."""
    client = auth_user["client"]
    t1 = client.post("/api/tasks", json={"title": "Bulk 1"}).get_json()["task"]
    t2 = client.post("/api/tasks", json={"title": "Bulk 2"}).get_json()["task"]

    # Bulk complete
    bc_res = client.post("/api/tasks/bulk-complete", json={"task_ids": [t1["id"], t2["id"]]})
    assert bc_res.status_code == 200
    assert bc_res.get_json()["count"] == 2

    # Bulk delete
    bd_res = client.post("/api/tasks/bulk-delete", json={"task_ids": [t1["id"], t2["id"]]})
    assert bd_res.status_code == 200
    assert bd_res.get_json()["count"] == 2

    # Verify both are deleted
    assert client.get(f"/api/tasks/{t1['id']}").status_code == 404
    assert client.get(f"/api/tasks/{t2['id']}").status_code == 404
