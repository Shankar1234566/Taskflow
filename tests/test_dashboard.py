from datetime import date, timedelta
import pytest

def test_dashboard_stats_calculation(auth_user):
    """Test dashboard total, pending, completed, overdue counts, and completion percentage."""
    client = auth_user["client"]
    today = date.today()
    yesterday = (today - timedelta(days=2)).isoformat()
    future = (today + timedelta(days=3)).isoformat()

    # Create 4 tasks:
    # 1: Completed task
    t1 = client.post("/api/tasks", json={"title": "Completed Task", "due_date": future}).get_json()["task"]
    client.patch(f"/api/tasks/{t1['id']}/complete")

    # 2: Incomplete, on-time task
    client.post("/api/tasks", json={"title": "Future Task", "due_date": future})

    # 3: Incomplete, overdue task
    client.post("/api/tasks", json={"title": "Overdue Task", "due_date": yesterday})

    # 4: Incomplete, no due date task
    client.post("/api/tasks", json={"title": "No Due Date Task"})

    # Test /api/dashboard
    res = client.get("/api/dashboard")
    assert res.status_code == 200
    data = res.get_json()
    assert data["total"] == 4
    assert data["completed"] == 1
    assert data["pending"] == 3
    assert data["overdue"] == 1
    assert data["completion_percentage"] == 25

    # Test /api/dashboard/stats for frontend donut and metrics cards
    stats_res = client.get("/api/dashboard/stats")
    assert stats_res.status_code == 200
    s_data = stats_res.get_json()
    assert s_data["total"] == 4
    assert s_data["completed"] == 1
    assert s_data["in_progress"] == 3
    assert s_data["overdue"] == 1
    assert s_data["percent_complete"] == 25
    assert "trends" in s_data
    assert s_data["trends"]["total"] == 4

def test_dashboard_user_isolation(auth_user, second_user):
    """Ensure dashboard statistics never aggregate or leak other users' task numbers."""
    client_a = auth_user["client"]
    client_b = second_user["client"]

    # User A creates 2 tasks
    client_a.post("/api/tasks", json={"title": "User A Task 1"})
    client_a.post("/api/tasks", json={"title": "User A Task 2"})

    # User B creates 1 task
    client_b.post("/api/tasks", json={"title": "User B Task 1"})

    # User A should only see 2 tasks
    stats_a = client_a.get("/api/dashboard").get_json()
    assert stats_a["total"] == 2

    # User B should only see 1 task
    stats_b = client_b.get("/api/dashboard").get_json()
    assert stats_b["total"] == 1

def test_dashboard_upcoming_calendar(auth_user):
    """Test /api/dashboard/upcoming returns due dates and upcoming list."""
    client = auth_user["client"]
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    client.post("/api/tasks", json={"title": "Upcoming 1", "due_date": tomorrow})

    res = client.get("/api/dashboard/upcoming")
    assert res.status_code == 200
    data = res.get_json()
    assert "due_dates" in data
    assert tomorrow in data["due_dates"]
    assert len(data["upcoming"]) >= 1
    assert data["upcoming"][0]["title"] == "Upcoming 1"

def test_unauthenticated_dashboard_rejected(client):
    """Unauthenticated client cannot access dashboard endpoints."""
    assert client.get("/api/dashboard").status_code == 401
    assert client.get("/api/dashboard/stats").status_code == 401
    assert client.get("/api/dashboard/upcoming").status_code == 401
