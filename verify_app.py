import json
import io
from app import create_app
from models import db, User, Team, Task

def test_everything():
    app = create_app()
    client = app.test_client()

    print("\n================== TASKFLOW AUTOMATED VERIFICATION ==================")

    # 1. Test Auth: Login as Admin
    print("\n1. Testing Auth Endpoints...")
    res = client.post("/api/auth/login", json={"email": "admin@taskflow.local", "password": "password123"})
    assert res.status_code == 200, f"Admin login failed: {res.data}"
    user_data = res.get_json()["user"]
    assert user_data["role"] == "Admin", "Admin role mismatch"
    print("  [PASS] POST /api/auth/login (Admin)")

    # 2. Test GET /api/auth/me
    res = client.get("/api/auth/me")
    assert res.status_code == 200
    assert res.get_json()["user"]["email"] == "admin@taskflow.local"
    print("  [PASS] GET /api/auth/me")

    # 3. Test Dashboard Stats
    print("\n2. Testing Dashboard & Team Stats...")
    res = client.get("/api/dashboard/stats")
    assert res.status_code == 200
    stats = res.get_json()
    assert stats["total"] >= 10, f"Expected at least 10 tasks, got {stats['total']}"
    assert stats["overdue"] >= 2, f"Expected at least 2 overdue tasks, got {stats['overdue']}"
    assert stats["in_review"] >= 2, f"Expected at least 2 in_review tasks, got {stats['in_review']}"
    print(f"  [PASS] GET /api/dashboard/stats -> Total: {stats['total']}, Overdue: {stats['overdue']}, In Review: {stats['in_review']}, Completed: {stats['completed']}")

    # 4. Test GET /api/teams (Admin only)
    res = client.get("/api/teams")
    assert res.status_code == 200
    teams = res.get_json()["teams"]
    assert len(teams) >= 2
    print(f"  [PASS] GET /api/teams -> Found {len(teams)} teams")

    # 5. Test GET /api/teams/members
    res = client.get("/api/teams/members")
    assert res.status_code == 200
    members = res.get_json()["members"]
    assert len(members) >= 4
    print(f"  [PASS] GET /api/teams/members -> Found {len(members)} engineers")

    # 6. Test GET /api/tasks (Admin view)
    print("\n3. Testing Task Endpoints & Scoping...")
    res = client.get("/api/tasks")
    assert res.status_code == 200
    tasks = res.get_json()["tasks"]
    assert len(tasks) >= 10
    print(f"  [PASS] GET /api/tasks -> Retrieved {len(tasks)} tasks")

    # 7. Test Logout and Login as Team Lead
    client.post("/api/auth/logout")
    res = client.post("/api/auth/login", json={"email": "lead_backend@taskflow.local", "password": "password123"})
    assert res.status_code == 200
    lead_user = res.get_json()["user"]
    print("  [PASS] Login as Team Lead (Sarah Jenkins, Backend Systems)")

    # 8. Team Lead: Create Task for Backend Engineer
    dev_backend_id = [m["id"] for m in members if m["email"] == "dev_backend@taskflow.local"][0]
    res = client.post("/api/tasks", json={
        "title": "Build Automated Verification Harness",
        "description": "Integration test harness validating all HTTP response codes.",
        "category": "Backend",
        "priority": "High",
        "due_date": "2026-10-30",
        "assigned_to_id": dev_backend_id,
        "team_id": lead_user["team_id"]
    })
    assert res.status_code == 201, f"Task creation failed: {res.data}"
    new_task = res.get_json()["task"]
    new_task_id = new_task["id"]
    print(f"  [PASS] POST /api/tasks (Lead created Task #{new_task_id})")

    # 9. Team Lead: Cannot assign to Frontend Engineer (cross-squad restriction)
    dev_frontend_id = [m["id"] for m in members if m["email"] == "dev_frontend@taskflow.local"][0]
    res = client.post("/api/tasks", json={
        "title": "Cross-squad Illegal Task",
        "category": "Frontend",
        "priority": "Low",
        "assigned_to_id": dev_frontend_id
    })
    assert res.status_code == 403, "Lead should not be able to assign task to another squad"
    print("  [PASS] Cross-Squad Isolation Enforced (403 Forbidden)")

    # 10. Login as Backend Member
    client.post("/api/auth/logout")
    res = client.post("/api/auth/login", json={"email": "dev_backend@taskflow.local", "password": "password123"})
    assert res.status_code == 200
    print("  [PASS] Login as Member (Alex Rivera)")

    # 11. Member: Transition task Pending -> In Progress
    res = client.patch(f"/api/tasks/{new_task_id}/status", json={"status": "In Progress"})
    assert res.status_code == 200
    assert res.get_json()["task"]["status"] == "In Progress"
    print(f"  [PASS] PATCH /api/tasks/{new_task_id}/status -> In Progress")

    # 12. Member: Submit Proof of Work
    proof_data = {
        "notes": "Completed test harness with 100% assertions passing.",
        "git_link": "https://github.com/enterprise/taskflow/pull/199",
        "proof_file": (io.BytesIO(b"Sample log file output: All tests passed."), "test_output.log")
    }
    res = client.post(f"/api/tasks/{new_task_id}/submit-proof", data=proof_data, content_type="multipart/form-data")
    assert res.status_code == 200
    task_in_review = res.get_json()["task"]
    assert task_in_review["status"] == "In Review"
    print(f"  [PASS] POST /api/tasks/{new_task_id}/submit-proof -> In Review")

    # 13. Member: Cannot review own task (Lead/Admin only)
    res = client.patch(f"/api/tasks/{new_task_id}/review", json={"action": "approve"})
    assert res.status_code == 403
    print("  [PASS] Member Forbidden from Approving (403 Forbidden)")

    # 14. Login as Lead to Review Task
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"email": "lead_backend@taskflow.local", "password": "password123"})
    
    # Lead Request Changes (Reject)
    res = client.patch(f"/api/tasks/{new_task_id}/review", json={"action": "reject", "feedback": "Add edge case assertions"})
    assert res.status_code == 200
    assert res.get_json()["task"]["status"] == "In Progress"
    print(f"  [PASS] PATCH /api/tasks/{new_task_id}/review (action: reject) -> Reverted to In Progress with feedback")

    # Re-submit proof
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"email": "dev_backend@taskflow.local", "password": "password123"})
    client.post(f"/api/tasks/{new_task_id}/submit-proof", data={"notes": "Added edge case tests.", "git_link": "https://github.com/enterprise/taskflow/pull/199"})

    # Lead Approve
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"email": "lead_backend@taskflow.local", "password": "password123"})
    res = client.patch(f"/api/tasks/{new_task_id}/review", json={"action": "approve", "feedback": "LGTM! Approved."})
    assert res.status_code == 200
    assert res.get_json()["task"]["status"] == "Completed"
    assert res.get_json()["task"]["completed"] is True
    print(f"  [PASS] PATCH /api/tasks/{new_task_id}/review (action: approve) -> Deliverable marked Completed")

    # 15. Delete Task
    res = client.delete(f"/api/tasks/{new_task_id}")
    assert res.status_code == 200
    print(f"  [PASS] DELETE /api/tasks/{new_task_id} -> Deleted successfully")

    # 16. Test AI Productivity Assistant Queries
    print("\n4. Testing AI Productivity Assistant (Dual-Engine / Rule-Based)...")
    queries = [
        "Which tasks are overdue?",
        "Summarize our team's progress.",
        "Draft a weekly status report.",
        "Break this deliverable into smaller subtasks."
    ]

    for q in queries:
        res = client.post("/api/assistant/query", json={"query": q})
        assert res.status_code == 200, f"Query '{q}' failed: {res.data}"
        body = res.get_json()
        assert "response" in body and body["response"], "Missing response field"
        assert "source" in body and body["source"] in ("ai", "rule_based"), f"Invalid source: {body.get('source')}"
        assert "model_badge" in body, "Missing model_badge"
        badge_repr = body['model_badge'].encode('ascii', 'replace').decode('ascii')
        print(f"  [PASS] POST /api/assistant/query ('{q}') -> Source: {body['source']}, Badge: '{badge_repr}'")
        first_line = body["response"].strip().split("\n")[0].encode('ascii', 'replace').decode('ascii')
        print(f"         Preview: {first_line}")

    # 17. Test Page Endpoints
    print("\n5. Testing HTML Page Routes...")
    res = client.get("/")
    assert res.status_code == 200, f"Index route failed: {res.status_code}"
    print("  [PASS] GET / -> 200 OK (index.html rendered)")

    client.post("/api/auth/logout")
    res = client.get("/")
    assert res.status_code == 302, "Unauthenticated GET / should redirect to /login"
    print("  [PASS] GET / (Unauthenticated) -> 302 Redirect to /login")

    res = client.get("/login")
    assert res.status_code == 200
    print("  [PASS] GET /login -> 200 OK (login.html rendered)")

    print("\n[SUCCESS] ALL TESTS AND VERIFICATION CHECKS PASSED PERFECTLY!\n")

if __name__ == "__main__":
    test_everything()
