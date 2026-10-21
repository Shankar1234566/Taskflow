from flask import Blueprint, session, jsonify
from models import db, ActivityLog
from routes.auth import login_required

activity_bp = Blueprint("activity", __name__)

@activity_bp.get("")
@activity_bp.get("/")
@login_required
def list_activities():
    """Retrieve the recent activity log for the current authenticated user."""
    user_id = session["user_id"]
    logs = ActivityLog.query.filter_by(user_id=user_id).order_by(ActivityLog.created_at.desc()).limit(50).all()
    return jsonify(activities=[log.to_dict() for log in logs]), 200

@activity_bp.delete("")
@activity_bp.delete("/")
@login_required
def clear_activities():
    """Clear activity history for the current authenticated user."""
    user_id = session["user_id"]
    ActivityLog.query.filter_by(user_id=user_id).delete()
    db.session.commit()
    return jsonify(ok=True, message="Activity history cleared."), 200
