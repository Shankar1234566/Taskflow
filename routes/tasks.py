import os
from datetime import date, datetime, timedelta, timezone
from flask import Blueprint, request, session, jsonify, current_app, send_from_directory
from werkzeug.utils import secure_filename
from models import db, Task, User, Team, ActivityLog
from utils.auth_decorators import login_required, role_required
from utils.validation import parse_optional_id
from services.notification_service import (
    notify_status_transition,
    notify_auto_routed_bug,
    notify_unblocked_dependents,
    notify_task_assigned,
    notify_review_requested,
    notify_feedback_submitted,
    add_watcher,
    remove_watcher,
    get_task_watchers,
    dispatch_event,
    EVENT_HIGH_PRIORITY_BUG
)
from routes.notifications import toggle_watch_logic, get_watch_status_logic

tasks_bp = Blueprint("tasks", __name__)
VALID_PRIORITIES = {"Critical", "High", "Medium", "Low"}
VALID_CATEGORIES = {"Frontend", "Backend", "Bug", "QA", "Docs", "Work", "Development", "Personal", "Design", "Study"}
VALID_STATUSES = {"Pending", "In Progress", "In Review", "Completed"}

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "uploads", "proofs")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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
    - Member / Employee: can view tasks within their team, or assigned/created by them.
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

    # Member / Employee: can access tasks in their team workspace or assigned/created by them
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
        raw_category = str(data.get("category") or "Frontend").strip()
        cleaned["category"] = raw_category[:50] if raw_category else "Frontend"
    elif not partial:
        cleaned["category"] = "Frontend"

    # Priority validation
    if "priority" in data:
        raw_priority = str(data.get("priority") or "Medium").strip().capitalize()
        if raw_priority not in VALID_PRIORITIES:
            return None, "Priority must be Critical, High, Medium, or Low."
        cleaned["priority"] = raw_priority
    elif not partial:
        cleaned["priority"] = "Medium"

    # Status validation
    if "status" in data:
        raw_status = str(data.get("status") or "").strip()
        if raw_status in VALID_STATUSES:
            cleaned["status"] = raw_status
            cleaned["completed"] = (raw_status == "Completed")
            if raw_status == "Completed":
                cleaned["completed_at"] = datetime.now(timezone.utc)
            else:
                cleaned["completed_at"] = None
    elif not partial:
        cleaned["status"] = "In Progress"
        cleaned["completed"] = False
        cleaned["completed_at"] = None

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
            cleaned["status"] = "Completed"
            cleaned["completed_at"] = datetime.now(timezone.utc)
        else:
            if not partial or "status" not in cleaned:
                cleaned["status"] = "In Progress"
            cleaned["completed_at"] = None

    # Enterprise Team & Assignee fields
    for field, label in (("team_id", "Team ID"), ("assigned_to_id", "Assignee ID")):
        if field not in data:
            continue
        parsed_id, error = parse_optional_id(data[field], label)
        if error:
            return None, error
        cleaned[field] = parsed_id

    return cleaned, None

@tasks_bp.get("")
@tasks_bp.get("/")
@login_required
def list_tasks():
    """
    Context-aware task retrieval:
    - Admin: can filter by ?team_id=X or view all squads with ?all=true.
    - Lead: returns all tasks belonging to their assigned team.
    - Member: returns only tasks where assigned_to_id == current_user.id.
    """
    current_user = get_current_user()
    if not current_user:
        return jsonify(error="Authentication required"), 401

    args = request.args
    today = date.today()
    query = Task.query

    # Role-based workspace isolation
    all_param = args.get("all", "").lower() in ("true", "1") or args.get("all_squads", "").lower() in ("true", "1")
    team_id = args.get("team_id", type=int)
    scope = (args.get("scope") or args.get("view") or "").strip().lower()

    if current_user.role == "Admin" or current_user.is_admin:
        if team_id:
            query = query.filter(Task.team_id == team_id)
        # Admin can view all tasks across company when no team_id filter is specified
    elif current_user.role == "Lead":
        if current_user.team_id:
            query = query.filter(db.or_(
                Task.team_id == current_user.team_id,
                Task.assigned_to_id == current_user.id,
                Task.user_id == current_user.id,
                Task.created_by_id == current_user.id
            ))
        else:
            query = query.filter(db.or_(
                Task.assigned_to_id == current_user.id,
                Task.user_id == current_user.id,
                Task.created_by_id == current_user.id
            ))
    else:
        # Software Engineer / Employee / Member
        if scope in ("my", "my-tasks") or args.get("assigned") == "me":
            query = query.filter(db.or_(
                Task.assigned_to_id == current_user.id,
                Task.user_id == current_user.id,
                Task.created_by_id == current_user.id
            ))
        elif current_user.team_id:
            # Team workspace view: shows all deliverables in designated team OR assigned directly to user OR created by user
            query = query.filter(db.or_(
                Task.team_id == current_user.team_id,
                Task.assigned_to_id == current_user.id,
                Task.user_id == current_user.id,
                Task.created_by_id == current_user.id
            ))
        else:
            query = query.filter(db.or_(
                Task.assigned_to_id == current_user.id,
                Task.user_id == current_user.id,
                Task.created_by_id == current_user.id
            ))

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
        query = query.filter(db.or_(Task.completed.is_(True), Task.status == "Completed"))
    elif status in ("pending", "in_progress"):
        query = query.filter(Task.completed.is_(False), Task.status == ("Pending" if status == "pending" else "In Progress"))
    elif status == "in_review":
        query = query.filter(Task.status == "In Review")
    elif status == "overdue":
        query = query.filter(Task.completed.is_(False), Task.status != "Completed", Task.due_date.is_not(None), Task.due_date < today)

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
    is_lead_or_admin = current_user.role in ("Admin", "Lead") or current_user.is_admin
    out = []
    for t in tasks:
        d = t.to_dict()
        if is_lead_or_admin:
            d["can_edit"] = True
        else:
            d["can_edit"] = bool(t.assigned_to_id == current_user.id or t.user_id == current_user.id)
        out.append(d)
    return jsonify(tasks=out), 200

def check_leave_conflict(assigned_to_id, due_date):
    """
    Checks if assigned employee is on approved leave during task due date.
    Returns warning message string if conflict exists, else None.
    """
    if not assigned_to_id or not due_date:
        return None
    try:
        from models import LeaveRequest
        due_date_str = due_date.strftime("%Y-%m-%d") if hasattr(due_date, "strftime") else str(due_date)[:10]
        active_leave = LeaveRequest.query.filter(
            LeaveRequest.user_id == assigned_to_id,
            LeaveRequest.status == "Approved",
            LeaveRequest.start_date <= due_date_str,
            LeaveRequest.end_date >= due_date_str
        ).first()
        if active_leave:
            assignee = db.session.get(User, assigned_to_id)
            name = (assignee.name if assignee and getattr(assignee, 'name', None) else (assignee.username if assignee else "Assignee"))
            return f"Warning: {name} is on approved leave from {active_leave.start_date} to {active_leave.end_date}."
    except Exception:
        pass
    return None

@tasks_bp.get("/check-conflict")
@login_required
def check_task_leave_conflict():
    user_id = request.args.get("assigned_to_id", type=int) or request.args.get("user_id", type=int)
    due_date = request.args.get("due_date", type=str)
    warning = check_leave_conflict(user_id, due_date)
    return jsonify(conflict=bool(warning), warning=warning, message=warning or ""), 200

@tasks_bp.post("")
@tasks_bp.post("/")
@login_required
def create_task():
    """
    Create and assign a task.
    - Leads and Admins can assign to direct reports (assigned_to_id).
    - Members can create deliverables assigned to themselves.
    """
    current_user = get_current_user()
    data = request.get_json(silent=True)
    if data is None:
        return jsonify(error="Invalid JSON body."), 400

    cleaned, error = validate_task_input(data, partial=False)
    if error:
        return jsonify(error=error), 400

    # Role permission check for assignee allocation
    assigned_to_id = cleaned.get("assigned_to_id")
    target_team_id = cleaned.get("team_id")
    was_auto_routed = False
    auto_assigned_engineer = None
    has_explicit_assignee = bool(data.get("assigned_to_id"))

    # Automated Bug & Deliverable Routing:
    # When a task of category "Bug" or "Defect" is created without an explicit assignee,
    # automatically route and assign it to the Team Lead or a designated On-Call/Default Engineer based on team settings.
    task_category = (cleaned.get("category") or "").strip()
    if task_category in ("Bug", "Defect") and not has_explicit_assignee:
        routing_team_id = target_team_id or current_user.team_id
        if routing_team_id:
            team_obj = db.session.get(Team, routing_team_id)
            if team_obj and getattr(team_obj, "auto_routing_enabled", True):
                if team_obj.default_bug_assignee_id:
                    auto_assigned_engineer = db.session.get(User, team_obj.default_bug_assignee_id)
                elif team_obj.lead_id:
                    auto_assigned_engineer = db.session.get(User, team_obj.lead_id)

                if auto_assigned_engineer:
                    assigned_to_id = auto_assigned_engineer.id
                    target_team_id = routing_team_id
                    was_auto_routed = True

    if assigned_to_id and not was_auto_routed:
        # If assigning to someone else, check privileges
        if assigned_to_id != current_user.id:
            if current_user.role not in ("Admin", "Lead") and not current_user.is_admin:
                return jsonify(error="Only Team Leads and Engineering Managers can assign tasks to other members."), 403

            assignee = db.session.get(User, assigned_to_id)
            if not assignee:
                return jsonify(error="Assignee user not found."), 404

            # If Team Lead, authority is scoped to employees in their designated squad
            if current_user.role == "Lead" and not current_user.is_admin:
                if current_user.team_id and assignee.team_id != current_user.team_id:
                    return jsonify(error="Team Leads can only assign tasks to employees within their designated squad."), 403

            task_user_id = assignee.id
            if not target_team_id or (current_user.role == "Lead" and not current_user.is_admin):
                target_team_id = current_user.team_id or assignee.team_id
        else:
            task_user_id = current_user.id
            if not target_team_id or (current_user.role == "Lead" and not current_user.is_admin):
                target_team_id = current_user.team_id
    elif was_auto_routed and auto_assigned_engineer:
        task_user_id = auto_assigned_engineer.id
    else:
        task_user_id = current_user.id
        assigned_to_id = current_user.id
        if not target_team_id or (current_user.role == "Lead" and not current_user.is_admin):
            target_team_id = current_user.team_id

    if target_team_id and not db.session.get(Team, target_team_id):
        return jsonify(error="Team not found."), 404

    # Optional dependency / blocker link
    blocked_by_id = data.get("blocked_by_id")
    if blocked_by_id:
        try:
            blocked_by_id = int(blocked_by_id)
            if not db.session.get(Task, blocked_by_id):
                blocked_by_id = None
        except (ValueError, TypeError):
            blocked_by_id = None

    initial_status = cleaned.get("status") or "Pending"
    task = Task(
        user_id=task_user_id,
        assigned_to_id=assigned_to_id,
        created_by_id=current_user.id,
        team_id=target_team_id,
        status=initial_status,
        blocked_by_id=blocked_by_id,
        **{k: v for k, v in cleaned.items() if k not in ("team_id", "assigned_to_id", "status")}
    )
    db.session.add(task)
    db.session.commit()

    # Automatically add creator and assignee as watchers
    add_watcher(task.id, current_user.id)
    if assigned_to_id:
        add_watcher(task.id, assigned_to_id)

    # Event-triggered notifications
    if was_auto_routed and auto_assigned_engineer:
        notify_auto_routed_bug(task, auto_assigned_engineer, actor_id=current_user.id)
    else:
        if assigned_to_id and assigned_to_id != current_user.id:
            notify_task_assigned(task, assigned_to_id, former_assignee_id=None, actor_id=current_user.id)
        if task_category in ("Bug", "Defect") and (task.priority or "").capitalize() in ("Critical", "High"):
            dispatch_event(
                EVENT_HIGH_PRIORITY_BUG,
                task,
                actor_id=current_user.id,
                priority="Urgent"
            )

    log_activity("created", task.title, task.id, f"Priority: {task.priority}, Category: {task.category}")
    db.session.commit()

    # Cross-Module Conflict Detection with Leave Management
    conflict_warn = check_leave_conflict(task.assigned_to_id, task.due_date)
    resp = {"task": task.to_dict(), "message": "Task created successfully."}
    if conflict_warn:
        resp["warning"] = conflict_warn
        resp["conflict_warning"] = conflict_warn
    return jsonify(**resp), 201

@tasks_bp.get("/<int:task_id>")
@login_required
def get_task(task_id):
    """Retrieve a single task with company hierarchy permissions."""
    current_user = get_current_user()
    task = get_accessible_task(task_id, current_user)
    if not task:
        return jsonify(error="Task not found."), 404
    d = task.to_dict()
    is_lead_or_admin = current_user.role in ("Admin", "Lead") or current_user.is_admin
    d["can_edit"] = True if is_lead_or_admin else bool(task.assigned_to_id == current_user.id or task.user_id == current_user.id)
    return jsonify(task=d), 200

@tasks_bp.put("/<int:task_id>")
@login_required
def update_task(task_id):
    """Update editable fields of a task."""
    current_user = get_current_user()
    task = get_accessible_task(task_id, current_user)
    if not task:
        return jsonify(error="Task not found."), 404

    # Action restriction: Members / Employees can only edit deliverables assigned to them
    if current_user.role in ("Member", "Employee") and not current_user.is_admin:
        if task.assigned_to_id != current_user.id and task.user_id != current_user.id:
            return jsonify(error="Action forbidden. Employees can only modify tasks assigned directly to them."), 403

    data = request.get_json(silent=True)
    if data is None:
        return jsonify(error="Invalid JSON body."), 400

    cleaned, error = validate_task_input(data, partial=True)
    if error:
        return jsonify(error=error), 400

    old_assignee_id = task.assigned_to_id
    old_status = task.status

    # If reassigning member
    if "assigned_to_id" in cleaned and cleaned["assigned_to_id"]:
        new_assignee_id = cleaned["assigned_to_id"]
        if new_assignee_id != task.assigned_to_id:
            if current_user.role not in ("Admin", "Lead") and not current_user.is_admin:
                return jsonify(error="Only Leads and Admins can reassign tasks."), 403
            assignee = db.session.get(User, new_assignee_id)
            if not assignee:
                return jsonify(error="Assignee user not found."), 404
            task.assigned_to_id = assignee.id
            task.user_id = assignee.id
            if not task.team_id and assignee.team_id:
                task.team_id = assignee.team_id

    if "team_id" in cleaned and cleaned["team_id"] and not db.session.get(Team, cleaned["team_id"]):
        return jsonify(error="Team not found."), 404

    for field, val in cleaned.items():
        if field not in ("assigned_to_id",):
            setattr(task, field, val)

    task.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    # Dispatch assignment & status change notifications
    if task.assigned_to_id != old_assignee_id:
        notify_task_assigned(task, task.assigned_to_id, old_assignee_id, actor_id=current_user.id)
    if task.status != old_status:
        notify_status_transition(task, old_status, task.status, actor_id=current_user.id)

    log_activity("updated", task.title, task.id)
    db.session.commit()

    d = task.to_dict()
    is_lead_or_admin = current_user.role in ("Admin", "Lead") or current_user.is_admin
    d["can_edit"] = True if is_lead_or_admin else bool(task.assigned_to_id == current_user.id or task.user_id == current_user.id)
    
    conflict_warn = check_leave_conflict(task.assigned_to_id, task.due_date)
    resp = {"task": d, "message": "Task updated successfully."}
    if conflict_warn:
        resp["warning"] = conflict_warn
        resp["conflict_warning"] = conflict_warn
    return jsonify(**resp), 200

@tasks_bp.patch("/<int:task_id>/status")
@login_required
def update_status(task_id):
    """Member status progression (e.g., Pending -> In Progress)."""
    current_user = get_current_user()
    task = get_accessible_task(task_id, current_user)
    if not task:
        return jsonify(error="Task not found."), 404

    # Action restriction: Members / Employees can only progress tasks assigned to them
    if current_user.role in ("Member", "Employee") and not current_user.is_admin:
        if task.assigned_to_id != current_user.id and task.user_id != current_user.id:
            return jsonify(error="Action forbidden. Employees can only update status for tasks assigned directly to them."), 403

    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    if new_status not in VALID_STATUSES:
        return jsonify(error="Invalid status transition."), 400

    old_status = task.status
    task.status = new_status
    if new_status == "Completed":
        task.completed = True
        task.completed_at = datetime.now(timezone.utc)
    else:
        task.completed = False
        task.completed_at = None

    task.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    # Trigger status change notification & blocker unblocking
    if old_status != new_status:
        notify_status_transition(task, old_status, new_status, actor_id=current_user.id)

    log_activity(f"status_{new_status.lower().replace(' ', '_')}", task.title, task.id)
    db.session.commit()

    return jsonify(task=task.to_dict(), message=f"Task transitioned to {new_status}."), 200

@tasks_bp.post("/<int:task_id>/submit-proof")
@login_required
def submit_proof_of_work(task_id):
    """
    Multipart form handler for Software Engineers to submit proof of work.
    Accepts:
    - notes: text implementation notes
    - git_link: Git PR or commit URL
    - proof_file: optional file attachment (screenshot, log, zip)
    Sets task status to 'In Review'.
    """
    current_user = get_current_user()
    task = get_accessible_task(task_id, current_user)
    if not task:
        return jsonify(error="Task not found."), 404

    # Extract fields from multipart or JSON
    if request.content_type and "multipart/form-data" in request.content_type:
        notes = request.form.get("notes") or request.form.get("submission_notes") or ""
        git_link = request.form.get("git_link") or request.form.get("git_repo_link") or ""
        proof_file = request.files.get("proof_file")
    else:
        data = request.get_json(silent=True) or {}
        notes = data.get("notes") or data.get("submission_notes") or ""
        git_link = data.get("git_link") or data.get("git_repo_link") or ""
        proof_file = None

    # Save uploaded file if present
    file_rel_path = task.proof_file_path
    if proof_file and proof_file.filename:
        filename = secure_filename(proof_file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved_name = f"{task.id}_{timestamp}_{filename}"
        proof_file.save(os.path.join(UPLOAD_FOLDER, saved_name))
        file_rel_path = f"/static/uploads/proofs/{saved_name}"

    task.submission_notes = notes.strip()
    task.git_repo_link = git_link.strip()
    if file_rel_path:
        task.proof_file_path = file_rel_path
    task.submitted_at = datetime.now(timezone.utc)
    task.status = "In Review"
    task.completed = False
    task.completed_at = None
    task.updated_at = datetime.now(timezone.utc)

    db.session.commit()
    notify_review_requested(task, actor_id=current_user.id)
    log_activity("submitted_proof", task.title, task.id, f"PR: {git_link[:60] if git_link else 'None'}")
    db.session.commit()

    return jsonify(task=task.to_dict(), message="Proof of work submitted. Deliverable is now In Review."), 200

@tasks_bp.patch("/<int:task_id>/review")
@role_required("Admin", "Lead")
def review_task(task_id):
    """
    Lead / Admin Review Pipeline endpoint.
    Accepts:
    - action: "approve" | "reject" | "changes_requested"
    - feedback: reviewer notes or revision instructions
    """
    current_user = get_current_user()
    task = get_accessible_task(task_id, current_user)
    if not task:
        return jsonify(error="Task not found."), 404

    data = request.get_json(silent=True) or {}
    action = (data.get("action") or "").lower()
    feedback = (data.get("feedback") or "").strip()

    if action not in ("approve", "reject", "changes_requested", "request_changes"):
        return jsonify(error="Review action must be 'approve' or 'reject'."), 400

    if action == "approve":
        task.status = "Completed"
        task.completed = True
        task.completed_at = datetime.now(timezone.utc)
        task.feedback_notes = feedback
        task.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        log_activity("approved_deliverable", task.title, task.id, f"Feedback: {feedback[:60] if feedback else 'Approved'}")
        msg = "Deliverable approved and marked as Completed."
    else:
        # Request changes / reject proof
        task.status = "In Progress"
        task.completed = False
        task.completed_at = None
        task.feedback_notes = feedback
        task.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        log_activity("requested_changes", task.title, task.id, f"Feedback: {feedback[:60]}")
        msg = "Revision requested. Deliverable reverted to In Progress with reviewer comments."

    db.session.commit()
    notify_feedback_submitted(task, actor_id=current_user.id, action=action, feedback=feedback)

    return jsonify(task=task.to_dict(), message=msg), 200

@tasks_bp.get("/uploads/<path:filename>")
@login_required
def serve_upload(filename):
    """Securely serve uploaded proof of work attachments."""
    return send_from_directory(UPLOAD_FOLDER, secure_filename(filename))

@tasks_bp.patch("/<int:task_id>/complete")
@login_required
def toggle_complete(task_id):
    """Toggle completion or set explicit completion state."""
    current_user = get_current_user()
    task = get_accessible_task(task_id, current_user)
    if not task:
        return jsonify(error="Task not found."), 404

    # Action restriction: Members / Employees can only complete deliverables assigned to them
    if current_user.role in ("Member", "Employee") and not current_user.is_admin:
        if task.assigned_to_id != current_user.id and task.user_id != current_user.id:
            return jsonify(error="Action forbidden. Employees can only complete deliverables assigned to them."), 403

    body = request.get_json(silent=True) or {}
    old_status = task.status
    if "completed" in body:
        task.completed = bool(body["completed"])
    else:
        task.completed = not task.completed

    if task.completed:
        task.status = "Completed"
        task.completed_at = datetime.now(timezone.utc)
        log_activity("completed", task.title, task.id)
    else:
        task.status = "In Progress"
        task.completed_at = None
        log_activity("reopened", task.title, task.id)

    task.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    if old_status != task.status:
        notify_status_transition(task, old_status, task.status, actor_id=current_user.id)
    if task.completed:
        notify_unblocked_dependents(task)

    d = task.to_dict()
    is_lead_or_admin = current_user.role in ("Admin", "Lead") or current_user.is_admin
    d["can_edit"] = True if is_lead_or_admin else bool(task.assigned_to_id == current_user.id or task.user_id == current_user.id)
    return jsonify(task=d, message="Task completion status updated."), 200

@tasks_bp.post("/<int:task_id>/star")
@login_required
def toggle_star(task_id):
    """Toggle starred/important status of a task."""
    current_user = get_current_user()
    task = get_accessible_task(task_id, current_user)
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
    current_user = get_current_user()
    task = get_accessible_task(task_id, current_user)
    if not task:
        return jsonify(error="Task not found."), 404

    clone = Task(
        user_id=session["user_id"],
        assigned_to_id=task.assigned_to_id or session["user_id"],
        created_by_id=session["user_id"],
        team_id=task.team_id,
        title=f"{task.title} (Copy)"[:200],
        description=task.description,
        category=task.category,
        priority=task.priority,
        status="Pending",
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
    """Delete a task."""
    current_user = get_current_user()
    task = get_accessible_task(task_id, current_user)
    if not task:
        return jsonify(error="Task not found."), 404

    # Action restriction: Members / Employees cannot delete teammates' deliverables
    if current_user.role in ("Member", "Employee") and not current_user.is_admin:
        if task.created_by_id != current_user.id and task.user_id != current_user.id:
            return jsonify(error="Action forbidden. Employees cannot delete teammates' tasks."), 403

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
    current_user = get_current_user()
    data = request.get_json(silent=True) or {}
    task_ids = data.get("task_ids") or []
    if not isinstance(task_ids, list) or not task_ids:
        return jsonify(error="No task IDs provided."), 400

    query = Task.query.filter(Task.id.in_(task_ids))
    if current_user.role != "Admin" and not current_user.is_admin:
        if current_user.role == "Lead" and current_user.team_id:
            query = query.filter(Task.team_id == current_user.team_id)
        else:
            query = query.filter(db.or_(Task.assigned_to_id == current_user.id, Task.user_id == current_user.id))

    tasks = query.all()
    now = datetime.now(timezone.utc)
    for t in tasks:
        t.completed = True
        t.status = "Completed"
        t.completed_at = now
        t.updated_at = now

    db.session.commit()
    for t in tasks:
        notify_unblocked_dependents(t)

    log_activity("bulk_completed", f"{len(tasks)} tasks", details=f"IDs: {task_ids}")
    db.session.commit()

    return jsonify(ok=True, count=len(tasks), message=f"{len(tasks)} tasks marked as completed."), 200

@tasks_bp.post("/bulk-delete")
@login_required
def bulk_delete():
    """Delete multiple tasks at once."""
    current_user = get_current_user()
    data = request.get_json(silent=True) or {}
    task_ids = data.get("task_ids") or []
    if not isinstance(task_ids, list) or not task_ids:
        return jsonify(error="No task IDs provided."), 400

    query = Task.query.filter(Task.id.in_(task_ids))
    if current_user.role != "Admin" and not current_user.is_admin:
        if current_user.role == "Lead" and current_user.team_id:
            query = query.filter(Task.team_id == current_user.team_id)
        else:
            query = query.filter(db.or_(Task.assigned_to_id == current_user.id, Task.user_id == current_user.id))

    tasks = query.all()
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
    order_map = data.get("order") or []
    if not isinstance(order_map, list):
        return jsonify(error="Invalid order mapping."), 400

    for item in order_map:
        tid = item.get("id")
        idx = item.get("order_index")
        if tid is not None and idx is not None:
            Task.query.filter_by(id=tid).update({"order_index": idx})

    db.session.commit()
    return jsonify(ok=True, message="Task order updated."), 200

@tasks_bp.post("/<int:task_id>/watch")
@login_required
def toggle_task_watch(task_id):
    """Toggle watch/subscribe status on deliverable for current user."""
    return toggle_watch_logic(task_id)

@tasks_bp.get("/<int:task_id>/watch-status")
@login_required
def get_task_watch_status(task_id):
    """Retrieve watch status and watcher count for deliverable."""
    return get_watch_status_logic(task_id)


# ==============================================================================
# SUBTASKS & ACCEPTANCE CRITERIA NESTED ENDPOINTS
# ==============================================================================
from routes.subtasks import (
    list_subtasks,
    create_subtask,
    batch_create_subtasks,
    ai_generate_subtasks,
    toggle_subtask,
    update_subtask,
    delete_subtask
)

tasks_bp.add_url_rule("/<int:task_id>/subtasks", "list_subtasks", list_subtasks, methods=["GET"])
tasks_bp.add_url_rule("/<int:task_id>/subtasks", "create_subtask", create_subtask, methods=["POST"])
tasks_bp.add_url_rule("/<int:task_id>/subtasks/batch", "batch_create_subtasks", batch_create_subtasks, methods=["POST"])
tasks_bp.add_url_rule("/<int:task_id>/subtasks/ai-generate", "ai_generate_subtasks", ai_generate_subtasks, methods=["POST"])
tasks_bp.add_url_rule("/<int:task_id>/subtasks/<int:subtask_id>/toggle", "toggle_task_subtask", toggle_subtask, methods=["PATCH", "POST"])
tasks_bp.add_url_rule("/<int:task_id>/subtasks/<int:subtask_id>", "update_task_subtask", update_subtask, methods=["PUT"])
tasks_bp.add_url_rule("/<int:task_id>/subtasks/<int:subtask_id>", "delete_task_subtask", delete_subtask, methods=["DELETE"])
