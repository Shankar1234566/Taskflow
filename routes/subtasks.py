from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, session
from models import db, Task, User, Subtask, ActivityLog
from utils.auth_decorators import login_required

subtasks_bp = Blueprint("subtasks", __name__)

def get_current_user():
    """Retrieve the currently authenticated User model."""
    uid = session.get("user_id")
    if not uid:
        return None
    return db.session.get(User, uid)

def get_accessible_task(task_id, current_user=None):
    """
    Retrieve a task respecting the company hierarchy:
    - Admin: can access any task.
    - Team Lead: can access tasks within their team, or assigned/created by them.
    - Member / Employee: can access tasks in their team workspace or assigned/created by them.
    """
    if current_user is None:
        current_user = get_current_user()
    if not current_user:
        return None

    task = db.session.get(Task, task_id)
    if not task:
        return None

    if current_user.role == "Admin" or current_user.is_admin:
        return task

    if current_user.role == "Lead":
        if current_user.team_id and task.team_id == current_user.team_id:
            return task
        if task.assigned_to_id == current_user.id or task.user_id == current_user.id or task.created_by_id == current_user.id:
            return task
        return None

    # Member: can access tasks in their team workspace or assigned/created by them
    if current_user.team_id and task.team_id == current_user.team_id:
        return task
    if task.assigned_to_id == current_user.id or task.user_id == current_user.id or task.created_by_id == current_user.id:
        return task

    return None

def log_activity(action, task_title, task_id=None, details=""):
    """Record an audit trail event for the current user."""
    try:
        user_id = session.get("user_id")
        if user_id:
            log = ActivityLog(
                user_id=user_id,
                action=action,
                task_id=task_id,
                task_title=task_title[:200],
                details=details[:255]
            )
            db.session.add(log)
    except Exception:
        pass

def compute_task_subtask_metrics(task):
    """Compute aggregate subtask statistics for a parent task."""
    subtasks = Subtask.query.filter_by(task_id=task.id).order_by(Subtask.order_index.asc()).all()
    total = len(subtasks)
    completed = sum(1 for s in subtasks if s.is_completed)
    progress_pct = round((completed / total * 100)) if total > 0 else 0
    return {
        "task_id": task.id,
        "total": total,
        "completed": completed,
        "progress_pct": progress_pct,
        "subtasks": [s.to_dict() for s in subtasks]
    }


# ==============================================================================
# SUBTASK API ENDPOINTS
# ==============================================================================

@login_required
def list_subtasks(task_id):
    """Retrieve all subtasks and completion metrics for a deliverable."""
    user = get_current_user()
    task = get_accessible_task(task_id, user)
    if not task:
        raw_task = db.session.get(Task, task_id)
        if raw_task:
            return jsonify(error="Forbidden. You do not have access to this deliverable."), 403
        return jsonify(error="Deliverable not found."), 404

    metrics = compute_task_subtask_metrics(task)
    return jsonify(metrics), 200


@login_required
def create_subtask(task_id):
    """Create a new subtask or acceptance checklist item under a deliverable."""
    user = get_current_user()
    task = get_accessible_task(task_id, user)
    if not task:
        raw_task = db.session.get(Task, task_id)
        if raw_task:
            return jsonify(error="Forbidden. You do not have access to this deliverable."), 403
        return jsonify(error="Deliverable not found."), 404

    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify(error="Subtask title is required."), 400
    if len(title) > 255:
        return jsonify(error="Subtask title must not exceed 255 characters."), 400

    highest_order = db.session.query(db.func.max(Subtask.order_index)).filter_by(task_id=task.id).scalar() or 0
    order_index = data.get("order_index", highest_order + 1)

    subtask = Subtask(
        task_id=task.id,
        title=title,
        is_completed=False,
        order_index=order_index
    )
    db.session.add(subtask)
    db.session.commit()

    log_activity("SUBTASK_ADDED", task.title, task.id, f"Added subtask: {title}")
    db.session.commit()

    metrics = compute_task_subtask_metrics(task)
    return jsonify({
        "message": "Subtask created successfully.",
        "subtask": subtask.to_dict(),
        "task_progress": metrics
    }), 201


@login_required
def batch_create_subtasks(task_id):
    """Create multiple subtasks in a single transactional batch."""
    user = get_current_user()
    task = get_accessible_task(task_id, user)
    if not task:
        raw_task = db.session.get(Task, task_id)
        if raw_task:
            return jsonify(error="Forbidden. You do not have access to this deliverable."), 403
        return jsonify(error="Deliverable not found."), 404

    data = request.get_json(silent=True) or {}
    items = data.get("subtasks", [])
    if not isinstance(items, list) or len(items) == 0:
        return jsonify(error="Expected a non-empty list of subtask items under 'subtasks'."), 400

    highest_order = db.session.query(db.func.max(Subtask.order_index)).filter_by(task_id=task.id).scalar() or 0
    created_subtasks = []

    for idx, item in enumerate(items):
        title = item.get("title") if isinstance(item, dict) else str(item)
        title = (title or "").strip()
        if not title:
            continue
        order_idx = highest_order + idx + 1
        subtask = Subtask(
            task_id=task.id,
            title=title[:255],
            is_completed=False,
            order_index=order_idx
        )
        db.session.add(subtask)
        created_subtasks.append(subtask)

    if not created_subtasks:
        return jsonify(error="No valid subtask titles provided."), 400

    db.session.commit()
    log_activity("SUBTASK_BATCH_ADDED", task.title, task.id, f"Added {len(created_subtasks)} subtasks")
    db.session.commit()

    metrics = compute_task_subtask_metrics(task)
    return jsonify({
        "message": f"Successfully created {len(created_subtasks)} subtasks.",
        "created_count": len(created_subtasks),
        "task_progress": metrics
    }), 201


@login_required
def ai_generate_subtasks(task_id):
    """
    Decompose deliverable into structured architectural milestones using
    domain heuristic decomposition aligned with category and title.
    """
    user = get_current_user()
    task = get_accessible_task(task_id, user)
    if not task:
        raw_task = db.session.get(Task, task_id)
        if raw_task:
            return jsonify(error="Forbidden. You do not have access to this deliverable."), 403
        return jsonify(error="Deliverable not found."), 404

    cat = (task.category or "Development").lower()
    t_title = task.title

    if "frontend" in cat or "design" in cat or "ui" in t_title.lower():
        templates = [
            f"Wireframe & Component Design Contract for '{t_title}'",
            "CSS Token Styling & Dark/Light Theme Compatibility",
            "Client-Side State Wiring & Form Validation Handlers",
            "API Client Integration & Asynchronous Fetch Guards",
            "Cross-Browser Testing & Responsive Viewport Verification"
        ]
    elif "database" in cat or "sql" in t_title.lower():
        templates = [
            f"Schema DDL Specification & Foreign Key Integrity Design",
            "SQLAlchemy ORM Entity Modeling & Index Optimization",
            "Non-Destructive SQLite Migration Script (apply_migrations)",
            "CRUD Transaction Handlers with Rollback Guardrails",
            "Automated Query Latency Benchmarks & Cascade Verification"
        ]
    else:  # Backend / General Systems
        templates = [
            f"RESTful API Contract & Authorization Header Specification",
            "Relational Model Schema & Foreign Key Relationship Mapping",
            "Core Domain Business Logic Implementation & Input Sanitization",
            "Automated Pytest Coverage Suite (Edge Cases & Auth Checks)",
            "Lead Review Pull Request Documentation & Verification Proof"
        ]

    highest_order = db.session.query(db.func.max(Subtask.order_index)).filter_by(task_id=task.id).scalar() or 0
    created = []
    for idx, title in enumerate(templates):
        subtask = Subtask(
            task_id=task.id,
            title=title,
            is_completed=False,
            order_index=highest_order + idx + 1
        )
        db.session.add(subtask)
        created.append(subtask)

    db.session.commit()
    log_activity("SUBTASK_AI_DECOMPOSED", task.title, task.id, f"Generated {len(created)} architectural subtasks")
    db.session.commit()

    metrics = compute_task_subtask_metrics(task)
    return jsonify({
        "message": f"Successfully generated {len(created)} architectural subtasks.",
        "subtasks": [s.to_dict() for s in created],
        "task_progress": metrics
    }), 201


@subtasks_bp.route("/<int:subtask_id>/toggle", methods=["PATCH", "POST"])
@login_required
def toggle_subtask(subtask_id, task_id=None):
    """Toggle completion status of a subtask."""
    user = get_current_user()
    subtask = db.session.get(Subtask, subtask_id)
    if not subtask:
        return jsonify(error="Subtask not found."), 404

    task = get_accessible_task(subtask.task_id, user)
    if not task:
        return jsonify(error="Forbidden. You do not have access to this deliverable."), 403

    subtask.is_completed = not subtask.is_completed
    subtask.completed_at = datetime.now(timezone.utc) if subtask.is_completed else None
    subtask.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    action_label = "SUBTASK_COMPLETED" if subtask.is_completed else "SUBTASK_REOPENED"
    log_activity(action_label, task.title, task.id, f"{'Completed' if subtask.is_completed else 'Reopened'} subtask: {subtask.title}")
    db.session.commit()

    metrics = compute_task_subtask_metrics(task)
    return jsonify({
        "message": "Subtask status updated.",
        "subtask": subtask.to_dict(),
        "task_progress": metrics
    }), 200


@subtasks_bp.route("/<int:subtask_id>", methods=["PUT"])
@login_required
def update_subtask(subtask_id, task_id=None):
    """Update subtask title or display order."""
    user = get_current_user()
    subtask = db.session.get(Subtask, subtask_id)
    if not subtask:
        return jsonify(error="Subtask not found."), 404

    task = get_accessible_task(subtask.task_id, user)
    if not task:
        return jsonify(error="Forbidden. You do not have access to this deliverable."), 403

    data = request.get_json(silent=True) or {}
    if "title" in data:
        title = (data.get("title") or "").strip()
        if not title:
            return jsonify(error="Subtask title cannot be empty."), 400
        if len(title) > 255:
            return jsonify(error="Subtask title must not exceed 255 characters."), 400
        subtask.title = title

    if "order_index" in data and isinstance(data["order_index"], int):
        subtask.order_index = data["order_index"]

    if "is_completed" in data and isinstance(data["is_completed"], bool):
        subtask.is_completed = data["is_completed"]
        subtask.completed_at = datetime.now(timezone.utc) if subtask.is_completed else None

    subtask.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    metrics = compute_task_subtask_metrics(task)
    return jsonify({
        "message": "Subtask updated successfully.",
        "subtask": subtask.to_dict(),
        "task_progress": metrics
    }), 200


@subtasks_bp.route("/<int:subtask_id>", methods=["DELETE"])
@login_required
def delete_subtask(subtask_id, task_id=None):
    """Delete a subtask permanently."""
    user = get_current_user()
    subtask = db.session.get(Subtask, subtask_id)
    if not subtask:
        return jsonify(error="Subtask not found."), 404

    task = get_accessible_task(subtask.task_id, user)
    if not task:
        return jsonify(error="Forbidden. You do not have access to this deliverable."), 403

    title_copy = subtask.title
    db.session.delete(subtask)
    db.session.commit()

    log_activity("SUBTASK_DELETED", task.title, task.id, f"Deleted subtask: {title_copy}")
    db.session.commit()

    metrics = compute_task_subtask_metrics(task)
    return jsonify({
        "message": "Subtask deleted successfully.",
        "subtask_id": subtask_id,
        "task_progress": metrics
    }), 200
