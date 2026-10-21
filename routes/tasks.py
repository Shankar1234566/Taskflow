from datetime import date, timedelta
from flask import Blueprint, request, session, jsonify
from models import db, Task
from .auth import login_required

tasks_bp = Blueprint("tasks", __name__)
PRIORITIES = {"High", "Medium", "Low"}

def own(tid):
    return Task.query.filter_by(id=tid, user_id=session["user_id"]).first()

def apply(t, d, partial=False):
    """Validate and copy fields onto a task. Returns an error string or None."""
    if "title" in d or not partial:
        title = (d.get("title") or "").strip()
        if not title: return "Title is required."
        t.title = title[:200]
    if "description" in d: t.description = d["description"] or ""
    if "category" in d: t.category = (d["category"] or "General")[:50]
    if "priority" in d:
        if d["priority"] not in PRIORITIES: return "Priority must be High, Medium, or Low."
        t.priority = d["priority"]
    if "due_date" in d:
        try: t.due_date = date.fromisoformat(d["due_date"]) if d["due_date"] else None
        except ValueError: return "Due date must be YYYY-MM-DD."

@tasks_bp.get("/")
@login_required
def list_tasks():
    q = Task.query.filter_by(user_id=session["user_id"])
    a, today = request.args, date.today()
    s = a.get("status")
    if s == "completed": q = q.filter(Task.completed.is_(True))
    elif s == "overdue": q = q.filter(Task.completed.is_(False), Task.due_date < today)
    elif s == "in_progress": q = q.filter(Task.completed.is_(False), db.or_(Task.due_date.is_(None), Task.due_date >= today))
    if a.get("priority"): q = q.filter_by(priority=a["priority"])
    if a.get("category"): q = q.filter_by(category=a["category"])
    if a.get("search"):
        like = f"%{a['search']}%"
        q = q.filter(db.or_(Task.title.ilike(like), Task.description.ilike(like)))
    if a.get("date"):
        try: q = q.filter(Task.due_date == date.fromisoformat(a["date"]))
        except ValueError: return jsonify(error="Invalid date."), 400
    elif a.get("due") == "today": q = q.filter(Task.due_date == today)
    elif a.get("due") == "week": q = q.filter(Task.due_date.between(today, today + timedelta(days=7)))
    tasks = q.order_by(Task.completed, Task.due_date.is_(None), Task.due_date).all()
    return jsonify(tasks=[t.to_dict() for t in tasks])

@tasks_bp.post("/")
@login_required
def create():
    t = Task(user_id=session["user_id"])
    err = apply(t, request.get_json(silent=True) or {})
    if err: return jsonify(error=err), 400
    db.session.add(t); db.session.commit()
    return jsonify(task=t.to_dict()), 201

@tasks_bp.get("/<int:tid>")
@login_required
def get(tid):
    t = own(tid)
    return jsonify(task=t.to_dict()) if t else (jsonify(error="Task not found."), 404)

@tasks_bp.put("/<int:tid>")
@login_required
def update(tid):
    t = own(tid)
    if not t: return jsonify(error="Task not found."), 404
    err = apply(t, request.get_json(silent=True) or {}, partial=True)
    if err: return jsonify(error=err), 400
    db.session.commit()
    return jsonify(task=t.to_dict())

@tasks_bp.delete("/<int:tid>")
@login_required
def delete(tid):
    t = own(tid)
    if not t: return jsonify(error="Task not found."), 404
    db.session.delete(t); db.session.commit()
    return jsonify(ok=True)

@tasks_bp.patch("/<int:tid>/complete")
@login_required
def complete(tid):
    t = own(tid)
    if not t: return jsonify(error="Task not found."), 404
    t.completed = not t.completed
    db.session.commit()
    return jsonify(task=t.to_dict())
