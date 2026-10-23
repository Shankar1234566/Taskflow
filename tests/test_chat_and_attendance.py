import pytest
from datetime import datetime, date
from models import db, User, Team, Task, ChatMessage, AttendanceRecord, LeaveRequest
from routes.chat_sockets import socketio

def test_attendance_check_in_out(app, client, auth_user):
    """Test attendance check-in, checkout, and today status calculation."""
    # 1. Today status before check-in
    res = client.get("/api/attendance/today")
    assert res.status_code == 200
    data = res.get_json()
    assert data["is_checked_in"] is False
    assert data["current_record"] is None

    # 2. Perform check-in
    res_in = client.post("/api/attendance/check-in")
    assert res_in.status_code in (200, 201)
    in_data = res_in.get_json()
    assert in_data["is_checked_in"] is True
    assert in_data["record"]["status"] == "Present"
    assert in_data["record"]["check_in_time"] is not None

    # 3. Today status after check-in
    res_status = client.get("/api/attendance/today")
    assert res_status.status_code == 200
    status_data = res_status.get_json()
    assert status_data["is_checked_in"] is True
    assert status_data["current_record"]["status"] == "Present"

    # 4. Perform check-out
    res_out = client.post("/api/attendance/check-out")
    assert res_out.status_code == 200
    out_data = res_out.get_json()
    assert out_data["is_checked_in"] is False
    assert out_data["record"]["check_out_time"] is not None
    assert "total_hours" in out_data["record"]

    # 5. Presence endpoint check
    res_pres = client.get("/api/attendance/presence")
    assert res_pres.status_code == 200
    pres_data = res_pres.get_json()
    uid = str(auth_user["user"]["id"])
    assert uid in pres_data["presence"]
    assert "is_checked_in" in pres_data["presence"][uid]

def test_leave_application_and_lead_approval(app, client, auth_user):
    """Test full leave workflow: employee applies, lead approves, presence reflects leave."""
    lead_id = auth_user["user"]["id"]

    # Create squad
    team_res = client.post("/api/teams", json={
        "name": "Platform Infrastructure",
        "description": "Core distributed systems squad",
        "lead_id": lead_id
    })
    assert team_res.status_code == 201
    team = team_res.get_json()["team"]

    # Create an employee member
    emp_client = app.test_client()
    emp_res = emp_client.post("/api/auth/register", json={
        "name": "Devin Torres",
        "email": "devin@example.com",
        "password": "Password123!",
        "role": "Member",
        "team_id": team["id"]
    })
    assert emp_res.status_code == 201
    emp_user = emp_res.get_json()["user"]

    # Employee submits leave request
    today_str = date.today().strftime('%Y-%m-%d')
    leave_payload = {
        "team_id": team["id"],
        "leave_type": "Paid",
        "start_date": today_str,
        "end_date": today_str,
        "reason": "Family vacation and restorative downtime"
    }
    apply_res = emp_client.post("/api/leaves/apply", json=leave_payload)
    assert apply_res.status_code == 201
    leave = apply_res.get_json()["leave"]
    assert leave["status"] == "Pending"
    assert leave["leave_type"] == "Paid"

    # Employee checks my leaves
    emp_leaves_res = emp_client.get("/api/leaves")
    assert emp_leaves_res.status_code == 200
    emp_leaves = emp_leaves_res.get_json()["leaves"]
    assert len(emp_leaves) == 1
    assert emp_leaves[0]["id"] == leave["id"]

    # Lead checks team leaves
    lead_leaves_res = client.get("/api/leaves")
    assert lead_leaves_res.status_code == 200
    lead_leaves = lead_leaves_res.get_json()["leaves"]
    assert any(l["id"] == leave["id"] for l in lead_leaves)

    # Lead approves leave
    action_res = client.patch(f"/api/leaves/{leave['id']}/action", json={
        "action": "approve",
        "comment": "Approved. Enjoy your time off!"
    })
    assert action_res.status_code == 200
    updated_leave = action_res.get_json()["leave"]
    assert updated_leave["status"] == "Approved"
    assert updated_leave["reviewed_by_id"] == lead_id

    # Verify presence shows on_leave = True for Devin
    pres_res = client.get("/api/attendance/presence")
    assert pres_res.status_code == 200
    pres_data = pres_res.get_json()
    emp_pres = pres_data["presence"].get(str(emp_user["id"]))
    assert emp_pres is not None
    assert emp_pres["on_leave"] is True
    assert emp_pres["leave_type"] == "Paid"

def test_workload_conflict_awareness(app, client, auth_user):
    """Test task assignment triggers conflict warning if assignee is on approved leave during due_date."""
    lead_id = auth_user["user"]["id"]

    # Create squad
    team_res = client.post("/api/teams", json={
        "name": "Backend DevOps",
        "lead_id": lead_id
    })
    team = team_res.get_json()["team"]

    # Create employee
    emp_client = app.test_client()
    emp_res = emp_client.post("/api/auth/register", json={
        "name": "Taylor Ray",
        "email": "taylor@example.com",
        "password": "Password123!",
        "role": "Member",
        "team_id": team["id"]
    })
    emp_user = emp_res.get_json()["user"]

    # Create and approve leave for Taylor for next week
    leave_res = emp_client.post("/api/leaves/apply", json={
        "team_id": team["id"],
        "leave_type": "Casual",
        "start_date": "2026-11-10",
        "end_date": "2026-11-15",
        "reason": "Personal medical appointment"
    })
    leave_id = leave_res.get_json()["leave"]["id"]
    client.patch(f"/api/leaves/{leave_id}/action", json={"action": "approve"})

    # 1. Check conflict via pre-validation endpoint
    chk_res = client.get(f"/api/tasks/check-conflict?assigned_to_id={emp_user['id']}&due_date=2026-11-12")
    assert chk_res.status_code == 200
    chk_data = chk_res.get_json()
    assert chk_data["conflict"] is True
    assert "approved leave" in chk_data["message"]
    assert "2026-11-10" in chk_data["message"]

    # 2. Check no conflict on a non-leave date
    chk_no_res = client.get(f"/api/tasks/check-conflict?assigned_to_id={emp_user['id']}&due_date=2026-11-20")
    assert chk_no_res.status_code == 200
    assert chk_no_res.get_json()["conflict"] is False

    # 3. Create task during leave period - should succeed but include warning notice
    task_res = client.post("/api/tasks", json={
        "title": "Upgrade PostgreSQL replica instances",
        "category": "Database",
        "priority": "High",
        "due_date": "2026-11-12",
        "assigned_to_id": emp_user["id"],
        "team_id": team["id"]
    })
    assert task_res.status_code == 201
    task_data = task_res.get_json()
    assert task_data["task"]["assigned_to_id"] == emp_user["id"]
    assert "conflict_warning" in task_data
    assert "Taylor Ray is on approved leave from 2026-11-10 to 2026-11-15" in task_data["conflict_warning"]

def test_instant_messaging_rest_and_channels(app, client, auth_user):
    """Test chat channel listing, message creation, and message fetching via REST APIs."""
    lead_id = auth_user["user"]["id"]

    # Create team
    team_res = client.post("/api/teams", json={
        "name": "Security & Auth Squad",
        "lead_id": lead_id
    })
    team = team_res.get_json()["team"]

    # Update user team_id
    with app.app_context():
        user = User.query.get(lead_id)
        user.team_id = team["id"]
        db.session.commit()

    # Create a task for squad discussion channel
    task_res = client.post("/api/tasks", json={
        "title": "Implement WebAuthn Biometrics",
        "category": "Backend",
        "priority": "Critical",
        "team_id": team["id"]
    })
    task = task_res.get_json()["task"]

    # 1. Fetch channels
    chan_res = client.get("/api/chat/channels")
    assert chan_res.status_code == 200
    channels = chan_res.get_json()["channels"]
    assert any(c["type"] == "team" and c["team_id"] == team["id"] for c in channels)
    assert any(c["type"] == "task" and c["task_id"] == task["id"] for c in channels)

    # 2. Post team message
    msg_res = client.post("/api/chat/messages", json={
        "team_id": team["id"],
        "content": "Sprint sync starting in 5 minutes in room A",
        "attachment_url": "https://example.com/meeting-agenda"
    })
    assert msg_res.status_code == 201
    msg_data = msg_res.get_json()["message"]
    assert msg_data["content"] == "Sprint sync starting in 5 minutes in room A"
    assert msg_data["attachment_url"] == "https://example.com/meeting-agenda"

    # 3. Post task thread message
    task_msg_res = client.post("/api/chat/messages", json={
        "team_id": team["id"],
        "task_id": task["id"],
        "content": "Spec review completed. Merging PR #42."
    })
    assert task_msg_res.status_code == 201

    # 4. Get team messages
    team_msgs_res = client.get(f"/api/chat/messages?team_id={team['id']}")
    assert team_msgs_res.status_code == 200
    team_msgs = team_msgs_res.get_json()["messages"]
    assert len(team_msgs) >= 1
    assert any(m["content"] == "Sprint sync starting in 5 minutes in room A" for m in team_msgs)

    # 5. Get task messages
    task_msgs_res = client.get(f"/api/chat/messages?team_id={team['id']}&task_id={task['id']}")
    assert task_msgs_res.status_code == 200
    task_msgs = task_msgs_res.get_json()["messages"]
    assert len(task_msgs) == 1
    assert task_msgs[0]["content"] == "Spec review completed. Merging PR #42."

def test_socketio_realtime_events(app, client, auth_user):
    """Test Flask-SocketIO event handlers: join_room, send_message, and broadcast."""
    lead_id = auth_user["user"]["id"]

    team_res = client.post("/api/teams", json={
        "name": "Distributed Realtime Squad",
        "lead_id": lead_id
    })
    team = team_res.get_json()["team"]

    # Use socketio test client attached to authenticated session
    socket_client = socketio.test_client(app, flask_test_client=client)
    assert socket_client.is_connected()

    # Join room
    socket_client.emit("join_room", {"team_id": team["id"]})

    # Send message via websocket event
    socket_client.emit("send_message", {
        "team_id": team["id"],
        "content": "Real-time socket message test",
        "attachment_url": None
    })

    # Check received events
    received = socket_client.get_received()
    message_events = [e for e in received if e["name"] == "new_message"]
    assert len(message_events) >= 1
    payload = message_events[0]["args"][0]
    assert payload["content"] == "Real-time socket message test"
    assert payload["sender_id"] == lead_id

    # Verify message was persisted in database
    with app.app_context():
        persisted = ChatMessage.query.filter_by(content="Real-time socket message test").first()
        assert persisted is not None
        assert persisted.sender_id == lead_id

    socket_client.disconnect()
