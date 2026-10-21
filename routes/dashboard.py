from datetime import date, datetime, timedelta
from flask import Blueprint, session, jsonify
from models import Task
from .auth import login_required

dashboard_bp = Blueprint("dashboard", __name__)

def mine():
    return Task.query.filter_by(user_id=session["user_id"])

@dashboard_bp.get("/stats")
@login_required
def stats():
    today, week = date.today(), datetime.utcnow() - timedelta(days=7)
    q = mine()
    total = q.count()
    completed = q.filter(Task.completed.is_(True)).count()
    overdue = q.filter(Task.completed.is_(False), Task.due_date < today).count()
    return jsonify(
        total=total, completed=completed, overdue=overdue, in_progress=total - completed,
        trends={"total": q.filter(Task.created_at >= week).count(),
                "completed": q.filter(Task.completed.is_(True), Task.updated_at >= week).count()},
        percent_complete=round(completed / total * 100) if total else 0)

@dashboard_bp.get("/upcoming")
@login_required
def upcoming():
    today = date.today()
    first = today.replace(day=1)
    nxt = (first + timedelta(days=32)).replace(day=1)
    month = mine().filter(Task.completed.is_(False), Task.due_date >= first, Task.due_date < nxt).all()
    soon = mine().filter(Task.completed.is_(False), Task.due_date >= today).order_by(Task.due_date).limit(5).all()
    return jsonify(due_dates=sorted({t.due_date.isoformat() for t in month}),
                   upcoming=[t.to_dict() for t in soon])
