from datetime import date, datetime, timedelta, timezone
from flask import Blueprint, session, jsonify
from models import Task
from .auth import login_required

dashboard_bp = Blueprint("dashboard", __name__)

def user_tasks():
    """Returns query for tasks belonging exclusively to current user."""
    return Task.query.filter_by(user_id=session["user_id"])

@dashboard_bp.get("")
@dashboard_bp.get("/")
@login_required
def dashboard_overview():
    """
    Returns high-level statistics for the current user's tasks:
    total, pending, completed, overdue, starred, today, and completion percentage.
    """
    today = date.today()
    q = user_tasks()
    total = q.count()
    completed = q.filter(Task.completed.is_(True)).count()
    pending = total - completed
    overdue = q.filter(Task.completed.is_(False), Task.due_date.is_not(None), Task.due_date < today).count()
    starred = q.filter(Task.is_starred.is_(True)).count()
    due_today = q.filter(Task.completed.is_(False), Task.due_date == today).count()
    percentage = round((completed / total) * 100) if total > 0 else 0

    return jsonify(
        total=total,
        pending=pending,
        in_progress=pending,
        completed=completed,
        overdue=overdue,
        starred=starred,
        due_today=due_today,
        completion_percentage=percentage,
        percent_complete=percentage
    ), 200

@dashboard_bp.get("/stats")
@login_required
def stats():
    """
    Full statistics including 7-day trend metrics and category breakdowns.
    """
    today = date.today()
    one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    q = user_tasks()
    total = q.count()
    completed = q.filter(Task.completed.is_(True)).count()
    pending = total - completed
    overdue = q.filter(Task.completed.is_(False), Task.due_date.is_not(None), Task.due_date < today).count()
    starred = q.filter(Task.is_starred.is_(True)).count()
    due_today = q.filter(Task.completed.is_(False), Task.due_date == today).count()
    percentage = round((completed / total) * 100) if total > 0 else 0

    # Group by category breakdown
    tasks = q.all()
    cat_map = {}
    for t in tasks:
        cat = t.category or "Work"
        if cat not in cat_map:
            cat_map[cat] = {"total": 0, "completed": 0}
        cat_map[cat]["total"] += 1
        if t.completed:
            cat_map[cat]["completed"] += 1

    categories_breakdown = [
        {"name": k, "total": v["total"], "completed": v["completed"], "percent": round((v["completed"] / v["total"]) * 100)}
        for k, v in sorted(cat_map.items())
    ]

    return jsonify(
        total=total,
        completed=completed,
        overdue=overdue,
        in_progress=pending,
        starred=starred,
        due_today=due_today,
        trends={
            "total": q.filter(Task.created_at >= one_week_ago).count(),
            "completed": q.filter(Task.completed.is_(True), Task.updated_at >= one_week_ago).count()
        },
        percent_complete=percentage,
        completion_percentage=percentage,
        categories=categories_breakdown
    ), 200

@dashboard_bp.get("/upcoming")
@login_required
def upcoming():
    """Returns due dates for the current calendar month and upcoming pending tasks."""
    today = date.today()
    first_of_month = today.replace(day=1)
    next_month = (first_of_month + timedelta(days=32)).replace(day=1)

    month_tasks = user_tasks().filter(
        Task.completed.is_(False),
        Task.due_date.is_not(None),
        Task.due_date >= first_of_month,
        Task.due_date < next_month
    ).all()

    upcoming_tasks = user_tasks().filter(
        Task.completed.is_(False),
        Task.due_date.is_not(None),
        Task.due_date >= today
    ).order_by(Task.due_date.asc()).limit(10).all()

    return jsonify(
        due_dates=sorted({t.due_date.isoformat() for t in month_tasks if t.due_date}),
        upcoming=[t.to_dict() for t in upcoming_tasks]
    ), 200
