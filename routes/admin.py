from functools import wraps
from datetime import date
from flask import Blueprint, session, jsonify, request
from models import db, User, Task, Team, ActivityLog
from routes.auth import login_required
from utils.validation import parse_optional_id

admin_bp = Blueprint("admin", __name__)

def admin_required(f):
    """Decorator to require administrator access."""
    @wraps(f)
    def wrap(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            return jsonify(error="Authentication required"), 401
        user = db.session.get(User, user_id)
        if not user or not user.is_admin:
            return jsonify(error="Administrator privileges required."), 403
        return f(*args, **kwargs)
    return wrap

@admin_bp.get("/stats")
@admin_required
def admin_stats():
    """System-wide metrics across all users for the Admin Dashboard."""
    today = date.today()
    total_users = User.query.count()
    total_tasks = Task.query.count()
    completed_tasks = Task.query.filter_by(completed=True).count()
    overdue_tasks = Task.query.filter(Task.completed.is_(False), Task.due_date.is_not(None), Task.due_date < today).count()
    total_activities = ActivityLog.query.count()
    completion_rate = round((completed_tasks / total_tasks) * 100) if total_tasks > 0 else 0

    return jsonify(
        total_users=total_users,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        overdue_tasks=overdue_tasks,
        completion_rate=completion_rate,
        total_activities=total_activities
    ), 200

@admin_bp.get("/users")
@admin_required
def list_users():
    """List all users with their aggregate task counts."""
    users = User.query.order_by(User.id.asc()).all()
    user_list = []
    for u in users:
        t_count = Task.query.filter(db.or_(Task.assigned_to_id == u.id, Task.user_id == u.id)).count()
        c_count = Task.query.filter(db.or_(Task.assigned_to_id == u.id, Task.user_id == u.id), db.or_(Task.completed.is_(True), Task.status == "Completed")).count()
        user_list.append({
            "id": u.id,
            "name": u.name,
            "username": u.username,
            "email": u.email,
            "role": u.role or ("Admin" if u.is_admin else "Member"),
            "team_id": u.team_id,
            "team_name": u.team.name if u.team else "Unassigned",
            "is_admin": bool(u.is_admin or u.role == "Admin"),
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "task_count": t_count,
            "completed_count": c_count
        })
    return jsonify(users=user_list), 200

@admin_bp.post("/users/<int:user_id>/toggle-admin")
@admin_required
def toggle_admin(user_id):
    """Promote or demote a user's administrator status."""
    if user_id == session.get("user_id"):
        return jsonify(error="Cannot remove admin status from your own active account."), 400

    target_user = db.session.get(User, user_id)
    if not target_user:
        return jsonify(error="User not found."), 404

    target_user.is_admin = not target_user.is_admin
    target_user.role = "Admin" if target_user.is_admin else "Member"
    db.session.commit()

    return jsonify(
        user=target_user.to_dict(),
        message=f"Admin rights {'granted to' if target_user.is_admin else 'revoked from'} {target_user.name}."
    ), 200

@admin_bp.post("/users/<int:user_id>/role")
@admin_required
def set_user_role(user_id):
    """Admin endpoint to update user role and squad assignment."""
    target_user = db.session.get(User, user_id)
    if not target_user:
        return jsonify(error="User not found."), 404

    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify(error="Invalid request payload. Expected JSON object."), 400
    new_role = data.get("role")
    new_team_id, error = parse_optional_id(data.get("team_id"), "Team ID")
    if error:
        return jsonify(error=error), 400
    if new_team_id and not db.session.get(Team, new_team_id):
        return jsonify(error="Team not found."), 404

    if new_role in ("Admin", "Lead", "Member"):
        target_user.role = new_role
        target_user.is_admin = (new_role == "Admin")

    if "team_id" in data:
        target_user.team_id = new_team_id if new_team_id else None

    db.session.commit()
    return jsonify(user=target_user.to_dict(), message=f"User {target_user.name} role updated to {target_user.role}."), 200

@admin_bp.delete("/users/<int:user_id>")
@admin_required
def delete_user(user_id):
    """Delete a user and all associated tasks/activities."""
    if user_id == session.get("user_id"):
        return jsonify(error="Cannot delete your own active admin account."), 400

    target_user = db.session.get(User, user_id)
    if not target_user:
        return jsonify(error="User not found."), 404

    db.session.delete(target_user)
    db.session.commit()

    return jsonify(ok=True, message=f"User {target_user.name} and all associated tasks were deleted."), 200
