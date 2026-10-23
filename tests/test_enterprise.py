import io
import pytest
from models import db, User, Team, Task

@pytest.fixture
def enterprise_squad(app):
    """Setup an enterprise structure with an Admin, a Team Lead, and a Member in a squad."""
    with app.app_context():
        # Create Admin
        admin = User(name="Sarah Admin", email="admin@enterprise.com", role="Admin", is_admin=True)
        admin.set_password("AdminPass123!")
        db.session.add(admin)
        db.session.commit()

        # Create Backend Squad
        squad = Team(name="Backend Squad", lead_id=None)
        db.session.add(squad)
        db.session.commit()

        # Create Lead
        lead = User(name="David Lead", email="lead@enterprise.com", role="Lead", is_admin=False, team_id=squad.id)
        lead.set_password("LeadPass123!")
        db.session.add(lead)
        db.session.commit()

        squad.lead_id = lead.id

        # Create Member
        member = User(name="Alice Engineer", email="alice@enterprise.com", role="Member", is_admin=False, team_id=squad.id)
        member.set_password("MemberPass123!")
        db.session.add(member)
        db.session.commit()

        return {
            "squad_id": squad.id,
            "admin_id": admin.id,
            "lead_id": lead.id,
            "member_id": member.id,
            "member_email": member.email,
            "lead_email": lead.email
        }

def login_client(app, email, password):
    client = app.test_client()
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return client

def test_enterprise_hierarchy_teams_listing(app, enterprise_squad):
    """Test GET /api/teams and GET /api/teams/members."""
    client = login_client(app, "admin@enterprise.com", "AdminPass123!")

    # List teams
    res = client.get("/api/teams")
    assert res.status_code == 200
    teams = res.get_json()["teams"]
    assert len(teams) >= 1
    backend_team = next(t for t in teams if t["name"] == "Backend Squad")
    assert backend_team["lead_name"] == "David Lead"

    # List members
    m_res = client.get(f"/api/teams/members?team_id={backend_team['id']}")
    assert m_res.status_code == 200
    members = m_res.get_json()["members"]
    emails = [m["email"] for m in members]
    assert "lead@enterprise.com" in emails
    assert "alice@enterprise.com" in emails

def test_team_endpoints_reject_invalid_lead_ids(app, enterprise_squad):
    client = login_client(app, "admin@enterprise.com", "AdminPass123!")

    invalid_lead = client.post("/api/teams", json={"name": "Invalid Lead", "lead_id": "not-an-id"})
    assert invalid_lead.status_code == 400
    assert invalid_lead.get_json()["error"] == "Lead ID must be a positive integer."

    missing_lead = client.post("/api/teams", json={"name": "Missing Lead", "lead_id": 999999})
    assert missing_lead.status_code == 404
    assert missing_lead.get_json()["error"] == "Lead user not found."

    invalid_target = client.patch(
        f"/api/teams/{enterprise_squad['squad_id']}/reassign",
        json={"target_team_id": "not-an-id", "task_ids": [1]}
    )
    assert invalid_target.status_code == 400
    assert invalid_target.get_json()["error"] == "Team ID must be a positive integer."

def test_lead_task_creation_and_member_isolation(app, enterprise_squad):
    """Lead creates a deliverable and assigns it to Alice (Member)."""
    lead_client = login_client(app, "lead@enterprise.com", "LeadPass123!")
    alice_id = enterprise_squad["member_id"]
    squad_id = enterprise_squad["squad_id"]

    # Lead creates task assigned to Alice
    payload = {
        "title": "Build Auth Rate Limiter",
        "description": "Token bucket rate limiting on /login",
        "category": "Backend",
        "priority": "High",
        "assigned_to_id": alice_id,
        "team_id": squad_id,
        "status": "Pending"
    }
    res = lead_client.post("/api/tasks", json=payload)
    assert res.status_code == 201
    task_data = res.get_json()["task"]
    assert task_data["assigned_to_id"] == alice_id
    assert task_data["status"] == "Pending"

    # Alice logs in and sees her deliverable
    alice_client = login_client(app, "alice@enterprise.com", "MemberPass123!")
    a_res = alice_client.get("/api/tasks")
    assert a_res.status_code == 200
    a_tasks = a_res.get_json()["tasks"]
    assert any(t["id"] == task_data["id"] for t in a_tasks)

def test_proof_of_work_submission_and_lead_review(app, enterprise_squad):
    """
    Full Proof of Work & Review Workflow:
    1. Member starts deliverable (Pending -> In Progress)
    2. Member submits Proof of Work (git PR link, notes, proof file) -> In Review
    3. Lead requests changes -> In Progress with feedback notes
    4. Member re-submits proof -> In Review
    5. Lead approves -> Completed
    """
    lead_client = login_client(app, "lead@enterprise.com", "LeadPass123!")
    alice_client = login_client(app, "alice@enterprise.com", "MemberPass123!")
    alice_id = enterprise_squad["member_id"]
    squad_id = enterprise_squad["squad_id"]

    # 1. Lead creates deliverable
    create_res = lead_client.post("/api/tasks", json={
        "title": "Migrate DB Indexes",
        "category": "Backend",
        "priority": "Critical",
        "assigned_to_id": alice_id,
        "team_id": squad_id,
        "status": "Pending"
    })
    tid = create_res.get_json()["task"]["id"]

    # 2. Alice starts progress
    start_res = alice_client.patch(f"/api/tasks/{tid}/status", json={"status": "In Progress"})
    assert start_res.status_code == 200
    assert start_res.get_json()["task"]["status"] == "In Progress"

    # 3. Alice submits proof of work (multipart form with attachment)
    proof_data = {
        "git_link": "https://github.com/company/backend/pull/42",
        "notes": "Added compound index on (team_id, status) and ran benchmarks.",
        "proof_file": (io.BytesIO(b"Benchmark logs: latency reduced from 120ms to 4ms"), "benchmarks.log")
    }
    proof_res = alice_client.post(f"/api/tasks/{tid}/submit-proof", data=proof_data, content_type="multipart/form-data")
    assert proof_res.status_code == 200
    task_in_review = proof_res.get_json()["task"]
    assert task_in_review["status"] == "In Review"
    assert task_in_review["git_repo_link"] == "https://github.com/company/backend/pull/42"
    assert "benchmarks.log" in task_in_review["proof_file_path"]

    # 4. Standard member cannot review deliverables (403 Forbidden)
    forbidden_review = alice_client.patch(f"/api/tasks/{tid}/review", json={"action": "approve"})
    assert forbidden_review.status_code == 403

    # 5. Lead requests revision
    rev_res = lead_client.patch(f"/api/tasks/{tid}/review", json={
        "action": "reject",
        "feedback": "Please add unit test checking index usage under SQLite EXPLAIN QUERY PLAN."
    })
    assert rev_res.status_code == 200
    rejected_task = rev_res.get_json()["task"]
    assert rejected_task["status"] == "In Progress"
    assert "EXPLAIN QUERY PLAN" in rejected_task["feedback_notes"]

    # 6. Alice re-submits proof
    reproof_res = alice_client.post(f"/api/tasks/{tid}/submit-proof", json={
        "git_link": "https://github.com/company/backend/pull/42",
        "notes": "Updated commit with query plan tests. Verified indexed scan."
    })
    assert reproof_res.status_code == 200
    assert reproof_res.get_json()["task"]["status"] == "In Review"

    # 7. Lead approves deliverable
    approve_res = lead_client.patch(f"/api/tasks/{tid}/review", json={
        "action": "approve",
        "feedback": "LGTM! Verified and approved."
    })
    assert approve_res.status_code == 200
    completed_task = approve_res.get_json()["task"]
    assert completed_task["status"] == "Completed"
    assert completed_task["completed"] is True
    assert completed_task["completed_at"] is not None

def test_employee_team_board_visibility_and_action_restrictions(app, enterprise_squad):
    """
    Test Employee scoping & collaboration rules:
    - Employee sees all team deliverables on the Team Board.
    - can_edit is True only for tasks assigned to the employee.
    - Employee cannot edit, delete, or complete a teammate's deliverable (403 Forbidden).
    - Scope filter ?scope=my returns strictly employee's deliverables.
    """
    with app.app_context():
        # Create a second member Bob in Backend Squad
        squad_id = enterprise_squad["squad_id"]
        bob = User(name="Bob Engineer", email="bob@enterprise.com", role="Employee", team_id=squad_id)
        bob.set_password("BobPass123!")
        db.session.add(bob)
        db.session.commit()
        bob_id = bob.id

    lead_client = login_client(app, "lead@enterprise.com", "LeadPass123!")
    alice_client = login_client(app, "alice@enterprise.com", "MemberPass123!")
    alice_id = enterprise_squad["member_id"]

    # Lead creates Alice's deliverable
    alice_task = lead_client.post("/api/tasks", json={
        "title": "Alice Deliverable",
        "category": "Backend",
        "assigned_to_id": alice_id,
        "team_id": squad_id
    }).get_json()["task"]

    # Lead creates Bob's deliverable
    bob_task = lead_client.post("/api/tasks", json={
        "title": "Bob Deliverable",
        "category": "Backend",
        "assigned_to_id": bob_id,
        "team_id": squad_id
    }).get_json()["task"]

    # Alice views team workspace (Team Board)
    team_res = alice_client.get("/api/tasks")
    assert team_res.status_code == 200
    tasks = team_res.get_json()["tasks"]
    task_map = {t["id"]: t for t in tasks}

    # Alice sees both tasks on the team board
    assert alice_task["id"] in task_map
    assert bob_task["id"] in task_map

    # Alice can edit her own task, but not Bob's
    assert task_map[alice_task["id"]]["can_edit"] is True
    assert task_map[bob_task["id"]]["can_edit"] is False

    # Alice toggles "My Deliverables" view (?scope=my)
    my_res = alice_client.get("/api/tasks?scope=my")
    assert my_res.status_code == 200
    my_tasks = my_res.get_json()["tasks"]
    assert any(t["id"] == alice_task["id"] for t in my_tasks)
    assert all(t["id"] != bob_task["id"] for t in my_tasks)

    # Alice attempts to edit Bob's task (Forbidden 403)
    edit_bob_res = alice_client.put(f"/api/tasks/{bob_task['id']}", json={"title": "Hacked Title"})
    assert edit_bob_res.status_code == 403

    # Alice attempts to complete Bob's task (Forbidden 403)
    complete_bob_res = alice_client.patch(f"/api/tasks/{bob_task['id']}/complete")
    assert complete_bob_res.status_code == 403

    # Alice attempts to delete Bob's task (Forbidden 403)
    delete_bob_res = alice_client.delete(f"/api/tasks/{bob_task['id']}")
    assert delete_bob_res.status_code == 403

    # Alice can successfully update her own task
    edit_alice_res = alice_client.put(f"/api/tasks/{alice_task['id']}", json={"title": "Alice Updated Title"})
    assert edit_alice_res.status_code == 200
    assert edit_alice_res.get_json()["task"]["title"] == "Alice Updated Title"

def test_team_lead_cross_team_isolation(app, enterprise_squad):
    """Team Leads cannot access, view, or review deliverables from other teams."""
    with app.app_context():
        frontend_squad = Team(name="Frontend Squad", lead_id=None)
        db.session.add(frontend_squad)
        db.session.commit()

        lead_fe = User(name="Frontend Lead", email="fe_lead@enterprise.com", role="Lead", team_id=frontend_squad.id)
        lead_fe.set_password("FeLeadPass123!")
        db.session.add(lead_fe)
        db.session.commit()
        frontend_squad.lead_id = lead_fe.id
        db.session.commit()
        fe_squad_id = frontend_squad.id

    fe_client = login_client(app, "fe_lead@enterprise.com", "FeLeadPass123!")
    fe_task = fe_client.post("/api/tasks", json={
        "title": "Design System Tokens",
        "category": "Frontend",
        "team_id": fe_squad_id
    }).get_json()["task"]

    # Backend Lead tries to access Frontend Lead's task
    be_lead_client = login_client(app, "lead@enterprise.com", "LeadPass123!")
    be_get_res = be_lead_client.get(f"/api/tasks/{fe_task['id']}")
    assert be_get_res.status_code == 404

    # Backend Lead tries to review Frontend Lead's task
    be_rev_res = be_lead_client.patch(f"/api/tasks/{fe_task['id']}/review", json={"action": "approve"})
    assert be_rev_res.status_code == 404

def test_team_members_alias_and_dashboard_stats(app, enterprise_squad):
    """Test /api/team/members alias and team-scoped dashboard stats."""
    lead_client = login_client(app, "lead@enterprise.com", "LeadPass123!")

    # Verify both /api/team/members and /api/teams/members work
    alias_res = lead_client.get("/api/team/members")
    assert alias_res.status_code == 200
    members = alias_res.get_json()["members"]
    assert any(m["email"] == "alice@enterprise.com" for m in members)

    # Verify GET /api/dashboard/stats returns role & team scoped metrics
    stats_res = lead_client.get("/api/dashboard/stats")
    assert stats_res.status_code == 200
    stats = stats_res.get_json()
    assert "total" in stats
    assert "in_progress" in stats
    assert "in_review" in stats
    assert "completed" in stats
    assert "overdue" in stats

def test_signup_as_team_lead_and_employee(app):
    """
    Test that an employee and a team lead can sign up to a designated squad,
    the team lead is assigned as the squad lead, and login requires only email and password.
    """
    client = app.test_client()

    with app.app_context():
        # Create a Designated Squad
        squad = Team(name="Mobile Squad")
        db.session.add(squad)
        db.session.commit()
        squad_id = squad.id

    # 1. Employee signs up to the Designated Squad
    emp_res = client.post("/api/auth/signup", json={
        "name": "Carlos Mobile Dev",
        "email": "carlos@enterprise.com",
        "password": "Password123!",
        "role": "Employee",
        "team_id": squad_id
    })
    assert emp_res.status_code == 201
    emp_user = emp_res.get_json()["user"]
    assert emp_user["role"] == "Member" or emp_user["role"] == "Employee"
    assert emp_user["team_id"] == squad_id

    # 2. Team Lead signs up to the Designated Squad
    lead_res = client.post("/api/auth/signup", json={
        "name": "Maria Lead",
        "email": "maria_lead@enterprise.com",
        "password": "Password123!",
        "role": "Lead",
        "team_id": squad_id
    })
    assert lead_res.status_code == 201
    lead_user = lead_res.get_json()["user"]
    assert lead_user["role"] == "Lead"
    assert lead_user["team_id"] == squad_id

    # Check that squad.lead_id was updated to Maria's user id
    with app.app_context():
        updated_squad = db.session.get(Team, squad_id)
        assert updated_squad.lead_id == lead_user["id"]

    # 3. Both can log in using ONLY email and password
    login_emp = client.post("/api/auth/login", json={
        "email": "carlos@enterprise.com",
        "password": "Password123!"
    })
    assert login_emp.status_code == 200
    assert login_emp.get_json()["user"]["email"] == "carlos@enterprise.com"

    login_lead = client.post("/api/auth/login", json={
        "email": "maria_lead@enterprise.com",
        "password": "Password123!"
    })
    assert login_lead.status_code == 200
    assert login_lead.get_json()["user"]["role"] == "Lead"

def test_team_lead_assignment_authority_scoped_to_designated_squad(app, enterprise_squad):
    """
    Test that a Team Lead can assign a task to an employee in their designated squad,
    but cannot assign to an employee outside their designated squad (receives 403).
    """
    with app.app_context():
        # Create QA Squad and QA Member
        qa_squad = Team(name="QA Squad")
        db.session.add(qa_squad)
        db.session.commit()

        qa_engineer = User(name="Quinn QA", email="quinn@enterprise.com", role="Member", team_id=qa_squad.id)
        qa_engineer.set_password("QaPass123!")
        db.session.add(qa_engineer)
        db.session.commit()
        qa_id = qa_engineer.id

    lead_client = login_client(app, "lead@enterprise.com", "LeadPass123!")
    alice_id = enterprise_squad["member_id"]

    # Team Lead assigns task to Alice (in the same squad) -> Allowed (201)
    res_success = lead_client.post("/api/tasks", json={
        "title": "Build SQL Migration for Order Indexes",
        "assigned_to_id": alice_id,
        "category": "Backend",
        "priority": "High"
    })
    assert res_success.status_code == 201
    assert res_success.get_json()["task"]["assigned_to_id"] == alice_id

    # Team Lead attempts to assign task to Quinn (outside their squad) -> Forbidden (403)
    res_forbidden = lead_client.post("/api/tasks", json={
        "title": "Execute Load Testing on Payment Gateway",
        "assigned_to_id": qa_id,
        "category": "QA",
        "priority": "Critical"
    })
    assert res_forbidden.status_code == 403
    assert "only assign tasks to employees within their designated squad" in res_forbidden.get_json()["error"]

def test_admin_monitor_performances_and_assign_to_team_lead(app, enterprise_squad):
    """
    Test that Admin can monitor individual squad performances (velocity, lead info)
    and assign tasks directly to Team Leads.
    """
    admin_client = login_client(app, "admin@enterprise.com", "AdminPass123!")
    lead_id = enterprise_squad["lead_id"]
    squad_id = enterprise_squad["squad_id"]

    # Admin checks stats and departments breakdown
    stats_res = admin_client.get("/api/dashboard/stats")
    assert stats_res.status_code == 200
    data = stats_res.get_json()
    assert "departments" in data
    departments = data["departments"]
    backend_dept = next(d for d in departments if d["team_id"] == squad_id)
    assert backend_dept["lead_name"] == "David Lead"
    assert backend_dept["lead_id"] == lead_id
    assert "velocity" in backend_dept

    # Admin assigns task directly to Team Lead
    task_res = admin_client.post("/api/tasks", json={
        "title": "Prepare Q3 Architecture Roadmap & Sprint Planning",
        "assigned_to_id": lead_id,
        "team_id": squad_id,
        "category": "Backend",
        "priority": "Critical"
    })
    assert task_res.status_code == 201
    task = task_res.get_json()["task"]
    assert task["assigned_to_id"] == lead_id
    assert task["team_id"] == squad_id

