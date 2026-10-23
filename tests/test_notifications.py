import pytest
from app import create_app
from models import db, User, Team, Task, Notification, TaskWatcher

@pytest.fixture
def app():
    app = create_app()
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False
    })

    with app.app_context():
        db.create_all()
        # Seed test squad
        team = Team(name="Engineering Alpha", auto_routing_enabled=True)
        db.session.add(team)
        db.session.commit()

        # Seed users: admin, lead, default engineer, member
        admin = User(username="Admin Sarah", email="admin@test.com", role="Admin", is_admin=True, team_id=team.id)
        admin.set_password("pass12345")

        lead = User(username="Lead Alex", email="lead@test.com", role="Lead", team_id=team.id)
        lead.set_password("pass12345")

        engineer = User(username="OnCall Engineer", email="oncall@test.com", role="Member", team_id=team.id)
        engineer.set_password("pass12345")

        member = User(username="Dev John", email="john@test.com", role="Member", team_id=team.id)
        member.set_password("pass12345")

        db.session.add_all([admin, lead, engineer, member])
        db.session.commit()

        team.lead_id = lead.id
        team.default_bug_assignee_id = engineer.id
        db.session.commit()

        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def login(client, email="john@test.com", password="pass12345"):
    return client.post("/api/auth/login", json={"email": email, "password": password})

def test_auto_route_bug_to_default_assignee(app, client):
    """When a bug is logged without explicit assignee, auto-routes to team's default bug assignee."""
    login(client, "john@test.com")
    res = client.post("/api/tasks", json={
        "title": "Fix critical payment deadlock",
        "description": "Database locks up on concurrent stripe webhooks",
        "category": "Bug",
        "priority": "Critical"
    })
    assert res.status_code == 201
    task_data = res.get_json()["task"]

    with app.app_context():
        oncall = User.query.filter_by(email="oncall@test.com").first()
        lead = User.query.filter_by(email="lead@test.com").first()
        assert task_data["assigned_to_id"] == oncall.id

        # Verify notification was dispatched to oncall engineer
        notif = Notification.query.filter_by(recipient_id=oncall.id, event_type="BUG_ROUTED").first()
        assert notif is not None
        assert "critical payment deadlock" in notif.message.lower()

        # Critical priority bug should also trigger alert for lead
        lead_alert = Notification.query.filter_by(recipient_id=lead.id).first()
        assert lead_alert is not None

def test_task_watching_and_status_transition_notifications(app, client):
    """Watching a task notifies subscriber when status moves from Pending -> In Progress -> Completed."""
    # Member creates task
    login(client, "john@test.com")
    create_res = client.post("/api/tasks", json={
        "title": "Build Auth Middleware",
        "category": "Backend",
        "priority": "High",
        "status": "Pending"
    })
    task_id = create_res.get_json()["task"]["id"]

    # Lead logs in and watches the deliverable
    login(client, "lead@test.com")
    watch_res = client.post(f"/api/tasks/{task_id}/watch")
    assert watch_res.status_code == 200
    assert watch_res.get_json()["is_watching"] is True
    assert watch_res.get_json()["watcher_count"] >= 2  # creator + lead

    status_res = client.get(f"/api/tasks/{task_id}/watch-status")
    assert status_res.status_code == 200
    assert status_res.get_json()["is_watching"] is True

    # Assignee moves task to In Progress
    login(client, "john@test.com")
    transition_res = client.patch(f"/api/tasks/{task_id}/status", json={"status": "In Progress"})
    assert transition_res.status_code == 200

    # Lead should receive status transition notification
    login(client, "lead@test.com")
    notif_res = client.get("/api/notifications?unread_only=true")
    assert notif_res.status_code == 200
    data = notif_res.get_json()
    assert data["unread_count"] >= 1
    found = any("In Progress" in n["message"] for n in data["notifications"])
    assert found is True

def test_unblocked_dependents_notification(app, client):
    """Completing a blocker task automatically alerts owner of dependent task ('Your deliverable is now unblocked!')."""
    login(client, "john@test.com")
    # Task A: Prerequisite
    res_a = client.post("/api/tasks", json={
        "title": "Design Database Schema",
        "category": "Backend"
    })
    task_a_id = res_a.get_json()["task"]["id"]

    # Task B: Blocked by Task A, assigned to oncall engineer
    with app.app_context():
        oncall = User.query.filter_by(email="oncall@test.com").first()
        oncall_id = oncall.id

    login(client, "lead@test.com")
    res_b = client.post("/api/tasks", json={
        "title": "Generate ORM Migrations",
        "category": "Backend",
        "assigned_to_id": oncall_id,
        "blocked_by_id": task_a_id
    })
    assert res_b.status_code == 201

    # John completes Task A
    login(client, "john@test.com")
    complete_res = client.patch(f"/api/tasks/{task_a_id}/complete", json={"completed": True})
    assert complete_res.status_code == 200

    # Oncall engineer checks notifications: should have BLOCKER_RESOLVED alert
    login(client, "oncall@test.com")
    notif_res = client.get("/api/notifications")
    assert notif_res.status_code == 200
    notifs = notif_res.get_json()["notifications"]
    blocker_alert = next((n for n in notifs if n["event_type"] == "BLOCKER_RESOLVED"), None)
    assert blocker_alert is not None
    assert "unblocked" in blocker_alert["message"].lower()

def test_notification_read_and_delete_endpoints(app, client):
    """Mark as read, mark all read, and delete notification."""
    with app.app_context():
        john = User.query.filter_by(email="john@test.com").first()
        n1 = Notification(recipient_id=john.id, event_type="TASK_ASSIGNED", title="Task 1", message="Msg 1")
        n2 = Notification(recipient_id=john.id, event_type="STATUS_CHANGED", title="Task 2", message="Msg 2")
        db.session.add_all([n1, n2])
        db.session.commit()
        n1_id = n1.id
        n2_id = n2.id

    login(client, "john@test.com")

    # Mark single read
    patch_res = client.patch(f"/api/notifications/{n1_id}/read")
    assert patch_res.status_code == 200
    assert patch_res.get_json()["notification"]["is_read"] is True

    # Mark all read
    read_all_res = client.patch("/api/notifications/read-all")
    assert read_all_res.status_code == 200
    assert read_all_res.get_json()["unread_count"] == 0

    # Delete notification
    del_res = client.delete(f"/api/notifications/{n2_id}")
    assert del_res.status_code == 200

    # Verify n2 is deleted
    with app.app_context():
        assert Notification.query.get(n2_id) is None
