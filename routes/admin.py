from functools import wraps
from datetime import date
from flask import Blueprint, session, jsonify, request
from models import db, User, Task, ActivityLog
from routes.auth import login_required

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
        t_count = Task.query.filter_by(user_id=u.id).count()
        c_count = Task.query.filter_by(user_id=u.id, completed=True).count()
        user_list.append({
            "id": u.id,
            "name": u.name,
            "username": u.username,
            "email": u.email,
            "is_admin": bool(u.is_admin),
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
    db.session.commit()

    return jsonify(
        user=target_user.to_dict(),
        message=f"Admin rights {'granted to' if target_user.is_admin else 'revoked from'} {target_user.name}."
    ), 200

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
