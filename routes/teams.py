from flask import Blueprint, session, jsonify, request
from models import db, Team, User, Task
from utils.auth_decorators import login_required, role_required
from utils.validation import parse_optional_id

teams_bp = Blueprint("teams", __name__)

@teams_bp.get("")
@teams_bp.get("/")
@role_required("Admin")
def list_teams():
    """List all company squads / teams."""
    teams = Team.query.order_by(Team.name.asc()).all()
    out = []
    for t in teams:
        members_count = User.query.filter_by(team_id=t.id).count()
        tasks_count = Task.query.filter_by(team_id=t.id).count()
        completed_count = Task.query.filter_by(team_id=t.id, status="Completed").count()
        in_review_count = Task.query.filter_by(team_id=t.id, status="In Review").count()
        velocity = round((completed_count / tasks_count) * 100) if tasks_count > 0 else 0

        lead = db.session.get(User, t.lead_id) if t.lead_id else None

        out.append({
            "id": t.id,
            "name": t.name,
            "lead_id": t.lead_id,
            "lead_name": lead.name if lead else None,
            "lead_email": lead.email if lead else None,
            "member_count": members_count,
            "task_count": tasks_count,
            "completed_count": completed_count,
            "in_review_count": in_review_count,
            "velocity": velocity,
            "created_at": t.created_at.isoformat() if t.created_at else None
        })
    return jsonify(teams=out), 200

@teams_bp.get("/members")
@login_required
def get_team_members():
    """
    Returns engineers for task assignment dropdown.
    - Admin: can query any team via ?team_id=X, or returns all active engineers across the company.
    - Team Lead: returns members belonging to their squad.
    - Member: returns teammates in their squad.
    """
    user_id = session.get("user_id")
    user = db.session.get(User, user_id)
    if not user:
        return jsonify(error="User not found"), 404

    target_team_id = request.args.get("team_id", type=int)

    query = User.query
    if target_team_id:
        query = query.filter_by(team_id=target_team_id)
    elif user.role == "Admin" or user.is_admin:
        # Admin can view all members if no team specified
        pass
    elif user.team_id:
        query = query.filter_by(team_id=user.team_id)

    members = query.order_by(User.username.asc()).all()
    out = []
    for m in members:
        team_name = m.team.name if m.team else "Unassigned Squad"
        out.append({
            "id": m.id,
            "name": m.name,
            "username": m.username,
            "email": m.email,
            "role": m.role or "Member",
            "team_id": m.team_id,
            "team_name": team_name
        })
    return jsonify(members=out), 200

@teams_bp.post("")
@teams_bp.post("/")
@role_required("Admin")
def create_team():
    """Admin endpoint to create a new squad / department."""
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify(error="Invalid request payload. Expected JSON object."), 400
    name = (data.get("name") or "").strip()
    lead_id, error = parse_optional_id(data.get("lead_id"), "Lead ID")
    if error:
        return jsonify(error=error), 400

    if not name:
        return jsonify(error="Team name is required."), 400

    if Team.query.filter_by(name=name).first():
        return jsonify(error="A squad with this name already exists."), 409

    if lead_id and not db.session.get(User, lead_id):
        return jsonify(error="Lead user not found."), 404

    team = Team(name=name[:50], lead_id=lead_id)
    db.session.add(team)
    db.session.commit()

    if lead_id:
        lead_user = db.session.get(User, lead_id)
        if lead_user:
            lead_user.team_id = team.id
            if lead_user.role != "Admin":
                lead_user.role = "Lead"
            db.session.commit()

    return jsonify(team=team.to_dict(), message="Squad created successfully."), 201

@teams_bp.patch("/<int:team_id>/reassign")
@role_required("Admin")
def reassign_team(team_id):
    """Admin endpoint to reassign squad lead or reallocate tickets between squads."""
    team = db.session.get(Team, team_id)
    if not team:
        return jsonify(error="Squad not found."), 404

    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify(error="Invalid request payload. Expected JSON object."), 400
    if "lead_id" in data:
        new_lead_id, error = parse_optional_id(data.get("lead_id"), "Lead ID")
        if error:
            return jsonify(error=error), 400
        if new_lead_id and not db.session.get(User, new_lead_id):
            return jsonify(error="Lead user not found."), 404
        team.lead_id = new_lead_id
        if new_lead_id:
            lead_user = db.session.get(User, new_lead_id)
            lead_user.team_id = team.id
            if lead_user.role != "Admin":
                lead_user.role = "Lead"

    # Reallocate tasks from this squad to another squad
    if "target_team_id" in data and "task_ids" in data:
        target_team_id, error = parse_optional_id(data.get("target_team_id"), "Team ID")
        if error or target_team_id is None:
            return jsonify(error=error or "Team ID is required."), 400
        if not db.session.get(Team, target_team_id):
            return jsonify(error="Target team not found."), 404
        task_ids = data.get("task_ids") or []
        if not isinstance(task_ids, list):
            return jsonify(error="Task IDs must be a list."), 400
        parsed_task_ids = []
        for task_id in task_ids:
            parsed_task_id, error = parse_optional_id(task_id, "Task ID")
            if error or parsed_task_id is None:
                return jsonify(error=error or "Task ID is required."), 400
            parsed_task_ids.append(parsed_task_id)
        if parsed_task_ids:
            Task.query.filter(Task.id.in_(parsed_task_ids)).update({Task.team_id: target_team_id}, synchronize_session=False)

    db.session.commit()
    return jsonify(team=team.to_dict(), message="Squad reallocation updated successfully."), 200
