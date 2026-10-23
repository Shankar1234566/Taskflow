from flask import Blueprint, request, session, jsonify
from models import db, Notification, TaskWatcher, Task, User
from utils.auth_decorators import login_required
from services.notification_service import add_watcher, remove_watcher

notifications_bp = Blueprint("notifications", __name__)

def get_current_user():
    """Retrieve currently authenticated User model."""
    uid = session.get("user_id")
    if not uid:
        return None
    return db.session.get(User, uid)

@notifications_bp.get("")
@notifications_bp.get("/")
@login_required
def get_notifications():
    """
    Returns paginated list of notifications for the authenticated user.
    Query parameters:
    - unread_only: 'true' | '1' (optional)
    - limit: int, default 20
    - page: int, default 1
    Returns:
    {
        "notifications": [...],
        "unread_count": int,
        "total": int
    }
    """
    user_id = session.get("user_id")
    unread_only_param = request.args.get("unread_only", "").strip().lower()
    unread_only = unread_only_param in ("true", "1")
    limit = request.args.get("limit", default=20, type=int)
    page = request.args.get("page", default=1, type=int)

    # Sanitize pagination parameters
    if limit < 1:
        limit = 20
    if limit > 100:
        limit = 100
    if page < 1:
        page = 1

    offset = (page - 1) * limit

    base_query = Notification.query.filter_by(recipient_id=user_id)
    unread_count = base_query.filter_by(is_read=False).count()

    filtered_query = base_query
    if unread_only:
        filtered_query = filtered_query.filter_by(is_read=False)

    total_count = filtered_query.count()
    items = filtered_query.order_by(Notification.created_at.desc()).offset(offset).limit(limit).all()

    return jsonify(
        notifications=[n.to_dict() for n in items],
        unread_count=unread_count,
        total=total_count,
        page=page,
        limit=limit
    ), 200


@notifications_bp.patch("/<int:notification_id>/read")
@login_required
def mark_notification_as_read(notification_id):
    """Mark a single notification as read."""
    user_id = session.get("user_id")
    notif = db.session.get(Notification, notification_id)
    if not notif:
        return jsonify(error="Notification not found."), 404

    if notif.recipient_id != user_id:
        return jsonify(error="Action forbidden. You do not own this notification."), 403

    notif.is_read = True
    db.session.commit()

    unread_count = Notification.query.filter_by(recipient_id=user_id, is_read=False).count()

    return jsonify(
        ok=True,
        notification=notif.to_dict(),
        unread_count=unread_count,
        message="Notification marked as read."
    ), 200


@notifications_bp.patch("/read-all")
@login_required
def mark_all_notifications_as_read():
    """Mark all unread notifications for current user as read."""
    user_id = session.get("user_id")
    updated_count = Notification.query.filter_by(recipient_id=user_id, is_read=False).update(
        {"is_read": True},
        synchronize_session="fetch"
    )
    db.session.commit()

    return jsonify(
        ok=True,
        updated_count=updated_count,
        unread_count=0,
        message="All notifications marked as read."
    ), 200


@notifications_bp.delete("/<int:notification_id>")
@login_required
def delete_notification(notification_id):
    """Delete / dismiss a notification."""
    user_id = session.get("user_id")
    notif = db.session.get(Notification, notification_id)
    if not notif:
        return jsonify(error="Notification not found."), 404

    if notif.recipient_id != user_id:
        return jsonify(error="Action forbidden. You do not own this notification."), 403

    db.session.delete(notif)
    db.session.commit()

    unread_count = Notification.query.filter_by(recipient_id=user_id, is_read=False).count()

    return jsonify(
        ok=True,
        unread_count=unread_count,
        message="Notification removed."
    ), 200


@notifications_bp.post("/tasks/<int:task_id>/watch")
@login_required
def toggle_task_watch_alias(task_id):
    """Toggles watch subscription on a task (alias endpoint)."""
    return toggle_watch_logic(task_id)


@notifications_bp.get("/tasks/<int:task_id>/watch-status")
@login_required
def get_task_watch_status_alias(task_id):
    """Retrieves watch status and watcher count for a task (alias endpoint)."""
    return get_watch_status_logic(task_id)


def toggle_watch_logic(task_id):
    user_id = session.get("user_id")
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify(error="Task not found."), 404

    existing = TaskWatcher.query.filter_by(task_id=task_id, user_id=user_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        is_watching = False
        msg = "You stopped watching this deliverable."
    else:
        new_watcher = TaskWatcher(task_id=task_id, user_id=user_id)
        db.session.add(new_watcher)
        db.session.commit()
        is_watching = True
        msg = "You are now watching this deliverable."

    count = TaskWatcher.query.filter_by(task_id=task_id).count()
    return jsonify(
        ok=True,
        is_watching=is_watching,
        watcher_count=count,
        message=msg
    ), 200


def get_watch_status_logic(task_id):
    user_id = session.get("user_id")
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify(error="Task not found."), 404

    existing = TaskWatcher.query.filter_by(task_id=task_id, user_id=user_id).first()
    count = TaskWatcher.query.filter_by(task_id=task_id).count()

    return jsonify(
        task_id=task_id,
        is_watching=bool(existing),
        watcher_count=count
    ), 200
