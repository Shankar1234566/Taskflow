from datetime import date, datetime, timedelta, timezone
from flask import Blueprint, request, session, jsonify
from models import db, Task, ActivityLog
from .auth import login_required

tasks_bp = Blueprint("tasks", __name__)
VALID_PRIORITIES = {"Critical", "High", "Medium", "Low"}

def get_user_task(task_id):
    """Retrieve a task only if it belongs to the authenticated user."""
    return Task.query.filter_by(id=task_id, user_id=session["user_id"]).first()

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

def validate_task_input(data, partial=False):
    """
    Validates and sanitizes task payload.
    Returns (cleaned_data, error_message).
    """
    if not isinstance(data, dict):
        return None, "Invalid request payload. Expected JSON object."

    cleaned = {}

    # Title validation
    if not partial or "title" in data:
        raw_title = data.get("title")
        if raw_title is None or not str(raw_title).strip():
            return None, "Title is required."
        cleaned["title"] = str(raw_title).strip()[:200]

    # Description validation
    if "description" in data:
        cleaned["description"] = str(data.get("description") or "").strip()
    elif not partial:
        cleaned["description"] = ""

    # Category validation
    if "category" in data:
        raw_category = str(data.get("category") or "Work").strip()
        cleaned["category"] = raw_category[:50] if raw_category else "Work"
    elif not partial:
        cleaned["category"] = "Work"

    # Priority validation
    if "priority" in data:
        raw_priority = str(data.get("priority") or "Medium").strip().capitalize()
        if raw_priority not in VALID_PRIORITIES:
            return None, "Priority must be Critical, High, Medium, or Low."
        cleaned["priority"] = raw_priority
    elif not partial:
        cleaned["priority"] = "Medium"

    # Due date validation
    if "due_date" in data:
        raw_due = data.get("due_date")
        if raw_due and str(raw_due).strip():
            try:
                cleaned["due_date"] = date.fromisoformat(str(raw_due).strip())
            except (ValueError, TypeError):
                return None, "Due date must be in YYYY-MM-DD format."
        else:
            cleaned["due_date"] = None
    elif not partial:
        cleaned["due_date"] = None

    # Due time validation
    if "due_time" in data:
        raw_time = str(data.get("due_time") or "").strip()
        cleaned["due_time"] = raw_time[:10] if raw_time else None

    # Tags validation
    if "tags" in data:
        raw_tags = data.get("tags")
        if isinstance(raw_tags, list):
            cleaned["tags"] = ", ".join(str(t).strip() for t in raw_tags if str(t).strip())[:255]
        else:
            cleaned["tags"] = str(raw_tags or "").strip()[:255]

    # Starred validation
    if "is_starred" in data:
        cleaned["is_starred"] = bool(data["is_starred"])

    # Completed flag validation
    if "completed" in data:
        cleaned["completed"] = bool(data["completed"])
        if cleaned["completed"]:
            cleaned["completed_at"] = datetime.now(timezone.utc)
        else:
            cleaned["completed_at"] = None
    elif not partial:
        cleaned["completed"] = False
        cleaned["completed_at"] = None

    return cleaned, None

@tasks_bp.get("")
@tasks_bp.get("/")
@login_required
def list_tasks():
    """List tasks belonging exclusively to current user with search, filter, and sort."""
    user_id = session["user_id"]
    query = Task.query.filter_by(user_id=user_id)
    args = request.args
    today = date.today()

    # Search filter (title, description, tags)
    search = (args.get("search") or "").strip()
    if search:
        like_pattern = f"%{search}%"
        query = query.filter(db.or_(
            Task.title.ilike(like_pattern),
            Task.description.ilike(like_pattern),
            Task.tags.ilike(like_pattern)
        ))

    # Status filter
    status = (args.get("status") or "").strip().lower()
    if status == "completed":
        query = query.filter(Task.completed.is_(True))
    elif status in ("pending", "in_progress"):
        query = query.filter(Task.completed.is_(False))
    elif status == "overdue":
        query = query.filter(Task.completed.is_(False), Task.due_date.is_not(None), Task.due_date < today)

    # Starred filter
    starred_arg = args.get("starred")
    if starred_arg is not None:
        if starred_arg.lower() in ("true", "1"):
            query = query.filter(Task.is_starred.is_(True))
        elif starred_arg.lower() in ("false", "0"):
            query = query.filter(Task.is_starred.is_(False))

    # Tag filter
    tag_arg = (args.get("tag") or "").strip()
    if tag_arg:
        query = query.filter(Task.tags.ilike(f"%{tag_arg}%"))

    # Priority filter
    priority = (args.get("priority") or "").strip()
    if priority:
        query = query.filter(Task.priority.ilike(priority))

    # Category filter
    category = (args.get("category") or "").strip()
    if category:
        query = query.filter(Task.category == category)

    # Date filter
    date_arg = args.get("date")
    if date_arg:
        try:
            parsed_date = date.fromisoformat(date_arg)
            query = query.filter(Task.due_date == parsed_date)
        except ValueError:
            return jsonify(error="Invalid date format. Use YYYY-MM-DD."), 400
    elif args.get("due") == "today":
        query = query.filter(Task.due_date == today)
    elif args.get("due") == "week":
        query = query.filter(Task.due_date.between(today, today + timedelta(days=7)))
    elif args.get("due") == "upcoming":
        query = query.filter(Task.completed.is_(False), Task.due_date.is_not(None), Task.due_date >= today)

    # Sorting
    sort_by = (args.get("sort") or "").lower()
    order = (args.get("order") or "asc").lower()

    if sort_by == "due_date":
        col = Task.due_date.desc() if order == "desc" else Task.due_date.asc()
        query = query.order_by(Task.due_date.is_(None), col)
    elif sort_by == "created_at":
        col = Task.created_at.desc() if order == "desc" else Task.created_at.asc()
        query = query.order_by(col)
    elif sort_by == "title":
        col = Task.title.desc() if order == "desc" else Task.title.asc()
        query = query.order_by(col)
    elif sort_by == "priority":
        # Order Critical -> High -> Medium -> Low
        priority_case = db.case(
            {"Critical": 1, "High": 2, "Medium": 3, "Low": 4},
            value=Task.priority,
            else_=5
        )
        col = priority_case.desc() if order == "desc" else priority_case.asc()
        query = query.order_by(col)
    else:
        # Default order: Incomplete first, Starred first, order_index asc, due_date soonest first
        query = query.order_by(
            Task.completed.asc(),
            Task.is_starred.desc(),
            Task.order_index.asc(),
            Task.due_date.is_(None).asc(),
            Task.due_date.asc(),
            Task.created_at.desc()
        )

    tasks = query.all()
    return jsonify(tasks=[t.to_dict() for t in tasks]), 200

@tasks_bp.post("")
@tasks_bp.post("/")
@login_required
def create_task():
    """Create a new task belonging to the authenticated user."""
    data = request.get_json(silent=True)
    if data is None:
        return jsonify(error="Invalid JSON body."), 400

    cleaned, error = validate_task_input(data, partial=False)
    if error:
        return jsonify(error=error), 400

    task = Task(user_id=session["user_id"], **cleaned)
    db.session.add(task)
    db.session.commit()

    log_activity("created", task.title, task.id, f"Priority: {task.priority}, Category: {task.category}")
    db.session.commit()

    return jsonify(task=task.to_dict(), message="Task created successfully."), 201

@tasks_bp.get("/<int:task_id>")
@login_required
def get_task(task_id):
    """Retrieve a single task belonging to the authenticated user."""
    task = get_user_task(task_id)
    if not task:
        return jsonify(error="Task not found."), 404
    return jsonify(task=task.to_dict()), 200

@tasks_bp.put("/<int:task_id>")
@login_required
def update_task(task_id):
    """Update editable fields of a task owned by the authenticated user."""
    task = get_user_task(task_id)
    if not task:
        return jsonify(error="Task not found."), 404

    data = request.get_json(silent=True)
    if data is None:
        return jsonify(error="Invalid JSON body."), 400

    cleaned, error = validate_task_input(data, partial=True)
    if error:
        return jsonify(error=error), 400

    for field, val in cleaned.items():
        setattr(task, field, val)

    task.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    log_activity("updated", task.title, task.id)
    db.session.commit()

    return jsonify(task=task.to_dict(), message="Task updated successfully."), 200

@tasks_bp.patch("/<int:task_id>/complete")
@login_required
def toggle_complete(task_id):
    """Toggle completion or set explicit completion state."""
    task = get_user_task(task_id)
    if not task:
        return jsonify(error="Task not found."), 404

    body = request.get_json(silent=True) or {}
    if "completed" in body:
        task.completed = bool(body["completed"])
    else:
        task.completed = not task.completed

    if task.completed:
        task.completed_at = datetime.now(timezone.utc)
        log_activity("completed", task.title, task.id)
    else:
        task.completed_at = None
        log_activity("reopened", task.title, task.id)

    task.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    return jsonify(task=task.to_dict(), message="Task completion status updated."), 200

@tasks_bp.post("/<int:task_id>/star")
@login_required
def toggle_star(task_id):
    """Toggle starred/important status of a task."""
    task = get_user_task(task_id)
    if not task:
        return jsonify(error="Task not found."), 404

    body = request.get_json(silent=True) or {}
    if "is_starred" in body:
        task.is_starred = bool(body["is_starred"])
    else:
        task.is_starred = not task.is_starred

    task.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    log_activity("starred" if task.is_starred else "unstarred", task.title, task.id)
    db.session.commit()

    return jsonify(task=task.to_dict(), message=f"Task {'starred' if task.is_starred else 'unstarred'}."), 200

@tasks_bp.post("/<int:task_id>/duplicate")
@login_required
def duplicate_task(task_id):
    """Create a duplicate copy of an existing task."""
    task = get_user_task(task_id)
    if not task:
        return jsonify(error="Task not found."), 404

    clone = Task(
        user_id=session["user_id"],
        title=f"{task.title} (Copy)"[:200],
        description=task.description,
        category=task.category,
        priority=task.priority,
        due_date=task.due_date,
        due_time=task.due_time,
        tags=task.tags,
        is_starred=task.is_starred,
        completed=False
    )
    db.session.add(clone)
    db.session.commit()

    log_activity("duplicated", clone.title, clone.id, f"Duplicated from #{task.id}")
    db.session.commit()

    return jsonify(task=clone.to_dict(), message="Task duplicated successfully."), 201

@tasks_bp.delete("/<int:task_id>")
@login_required
def delete_task(task_id):
    """Delete a task owned by the authenticated user."""
    task = get_user_task(task_id)
    if not task:
        return jsonify(error="Task not found."), 404

    title = task.title
    db.session.delete(task)
    db.session.commit()

    log_activity("deleted", title, task_id)
    db.session.commit()

    return jsonify(ok=True, message="Task deleted successfully."), 200

@tasks_bp.post("/bulk-complete")
@login_required
def bulk_complete():
    """Mark multiple tasks as completed."""
    data = request.get_json(silent=True) or {}
    task_ids = data.get("task_ids") or []
    if not isinstance(task_ids, list) or not task_ids:
        return jsonify(error="No task IDs provided."), 400

    tasks = Task.query.filter(Task.user_id == session["user_id"], Task.id.in_(task_ids)).all()
    now = datetime.now(timezone.utc)
    for t in tasks:
        t.completed = True
        t.completed_at = now
        t.updated_at = now

    db.session.commit()
    log_activity("bulk_completed", f"{len(tasks)} tasks", details=f"IDs: {task_ids}")
    db.session.commit()

    return jsonify(ok=True, count=len(tasks), message=f"{len(tasks)} tasks marked as completed."), 200

@tasks_bp.post("/bulk-delete")
@login_required
def bulk_delete():
    """Delete multiple tasks at once."""
    data = request.get_json(silent=True) or {}
    task_ids = data.get("task_ids") or []
    if not isinstance(task_ids, list) or not task_ids:
        return jsonify(error="No task IDs provided."), 400

    tasks = Task.query.filter(Task.user_id == session["user_id"], Task.id.in_(task_ids)).all()
    count = len(tasks)
    for t in tasks:
        db.session.delete(t)

    db.session.commit()
    log_activity("bulk_deleted", f"{count} tasks", details=f"IDs: {task_ids}")
    db.session.commit()

    return jsonify(ok=True, count=count, message=f"{count} tasks deleted."), 200

@tasks_bp.post("/reorder")
@login_required
def reorder_tasks():
    """Update custom sorting order_index for tasks."""
    data = request.get_json(silent=True) or {}
    order_map = data.get("order") or []  # List of {id: int, order_index: int}
    if not isinstance(order_map, list):
        return jsonify(error="Invalid order mapping."), 400

    for item in order_map:
        tid = item.get("id")
        idx = item.get("order_index")
        if tid is not None and idx is not None:
            Task.query.filter_by(id=tid, user_id=session["user_id"]).update({"order_index": idx})

    db.session.commit()
    return jsonify(ok=True, message="Task order updated."), 200
