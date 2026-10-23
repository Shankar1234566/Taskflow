from datetime import date, datetime, timedelta, timezone
from flask import Blueprint, session, jsonify, request
from models import db, Task, User, Team
from utils.auth_decorators import login_required

dashboard_bp = Blueprint("dashboard", __name__)

def get_role_scoped_task_query(current_user, team_id_override=None, all_company=False):
    """
    Returns base Task query scoped by role:
    - Admin: Global access across all company squads if all_company is True, or filtered by team_id_override.
             Otherwise scoped to tasks assigned to or created by current_user.
    - Lead: All tasks strictly belonging to lead's squad (current_user.team_id).
    - Member / Employee: All tasks strictly belonging to member's squad (current_user.team_id) or assigned to them.
    """
    query = Task.query
    if team_id_override:
        query = query.filter(Task.team_id == team_id_override)
    elif all_company and (current_user.role == "Admin" or current_user.is_admin):
        pass  # Global access for Admin across all company
    elif current_user.role in ("Lead", "Member", "Employee") and current_user.team_id:
        query = query.filter(Task.team_id == current_user.team_id)
    else:
        query = query.filter(db.or_(
            Task.assigned_to_id == current_user.id,
            Task.user_id == current_user.id,
            Task.created_by_id == current_user.id
        ))
    return query

@dashboard_bp.get("")
@dashboard_bp.get("/")
@login_required
def dashboard_overview():
    """
    Returns high-level statistics based on role:
    total, pending, in_progress, in_review, completed, overdue, starred, today, and completion percentage.
    """
    user_id = session.get("user_id")
    user = db.session.get(User, user_id)
    if not user:
        return jsonify(error="Authentication required"), 401

    args = request.args
    team_id_arg = args.get("team_id", type=int)
    all_arg = args.get("all", "").lower() in ("true", "1")
    today = date.today()
    q = get_role_scoped_task_query(user, team_id_arg, all_arg)

    total = q.count()
    completed = q.filter(db.or_(Task.completed.is_(True), Task.status == "Completed")).count()
    in_review = q.filter(Task.status == "In Review").count()
    in_progress = q.filter(Task.status == "In Progress").count()
    pending = total - completed
    overdue = q.filter(
        Task.completed.is_(False),
        Task.status != "Completed",
        Task.due_date.is_not(None),
        Task.due_date < today
    ).count()
    starred = q.filter(Task.is_starred.is_(True)).count()
    due_today = q.filter(
        Task.completed.is_(False),
        Task.status != "Completed",
        Task.due_date == today
    ).count()
    percentage = round((completed / total) * 100) if total > 0 else 0

    return jsonify(
        total=total,
        pending=pending,
        in_progress=in_progress,
        in_review=in_review,
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
    Full role-aware statistics including Pending, In Progress, In Review,
    Completed, Overdue, 7-day trend metrics, and category & squad breakdowns.
    """
    user_id = session.get("user_id")
    user = db.session.get(User, user_id)
    if not user:
        return jsonify(error="Authentication required"), 401

    args = request.args
    team_id_arg = args.get("team_id", type=int)
    all_arg = args.get("all", "").lower() in ("true", "1") or (user.role == "Admin" or user.is_admin)
    today = date.today()
    one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    q = get_role_scoped_task_query(user, team_id_arg, all_arg)

    total = q.count()
    completed = q.filter(db.or_(Task.completed.is_(True), Task.status == "Completed")).count()
    in_review = q.filter(Task.status == "In Review").count()
    in_progress = q.filter(Task.status == "In Progress").count()
    pending = q.filter(Task.status == "Pending").count()
    overdue = q.filter(
        Task.completed.is_(False),
        Task.status != "Completed",
        Task.due_date.is_not(None),
        Task.due_date < today
    ).count()
    starred = q.filter(Task.is_starred.is_(True)).count()
    due_today = q.filter(
        Task.completed.is_(False),
        Task.status != "Completed",
        Task.due_date == today
    ).count()
    percentage = round((completed / total) * 100) if total > 0 else 0

    # Group by category breakdown
    tasks = q.all()
    cat_map = {}
    for t in tasks:
        cat = t.category or "Frontend"
        if cat not in cat_map:
            cat_map[cat] = {"total": 0, "completed": 0, "in_review": 0}
        cat_map[cat]["total"] += 1
        if t.completed or t.status == "Completed":
            cat_map[cat]["completed"] += 1
        elif t.status == "In Review":
            cat_map[cat]["in_review"] += 1

    categories_breakdown = [
        {
            "name": k,
            "total": v["total"],
            "completed": v["completed"],
            "in_review": v["in_review"],
            "percent": round((v["completed"] / v["total"]) * 100) if v["total"] > 0 else 0
        }
        for k, v in sorted(cat_map.items())
    ]

    # Department breakdown (for Admin / Lead high-level command center)
    departments = []
    if user.role in ("Admin", "Lead") or user.is_admin:
        all_teams = Team.query.order_by(Team.name.asc()).all()
        for tm in all_teams:
            t_total = Task.query.filter_by(team_id=tm.id).count()
            t_comp = Task.query.filter(Task.team_id == tm.id, db.or_(Task.completed.is_(True), Task.status == "Completed")).count()
            t_rev = Task.query.filter_by(team_id=tm.id, status="In Review").count()
            t_prog = Task.query.filter_by(team_id=tm.id, status="In Progress").count()
            t_pend = Task.query.filter_by(team_id=tm.id, status="Pending").count()
            t_over = Task.query.filter(
                Task.team_id == tm.id,
                Task.completed.is_(False),
                Task.status != "Completed",
                Task.due_date.is_not(None),
                Task.due_date < today
            ).count()
            rate = round((t_comp / t_total) * 100) if t_total > 0 else 0
            departments.append({
                "team_id": tm.id,
                "team_name": tm.name,
                "lead_id": tm.lead_id,
                "lead_name": tm.lead.name if tm.lead else "Unassigned",
                "total": t_total,
                "completed": t_comp,
                "in_review": t_rev,
                "in_progress": t_prog,
                "pending": t_pend,
                "overdue": t_over,
                "velocity": rate
            })

    return jsonify(
        total=total,
        completed=completed,
        overdue=overdue,
        in_progress=in_progress,
        pending=pending,
        in_review=in_review,
        starred=starred,
        due_today=due_today,
        trends={
            "total": q.filter(Task.created_at >= one_week_ago).count(),
            "completed": q.filter(db.or_(Task.completed.is_(True), Task.status == "Completed"), Task.updated_at >= one_week_ago).count()
        },
        percent_complete=percentage,
        completion_percentage=percentage,
        categories=categories_breakdown,
        departments=departments
    ), 200

@dashboard_bp.get("/upcoming")
@login_required
def upcoming():
    """Returns due dates for the current calendar month and upcoming pending tasks."""
    user_id = session.get("user_id")
    user = db.session.get(User, user_id)
    if not user:
        return jsonify(error="Authentication required"), 401

    today = date.today()
    first_of_month = today.replace(day=1)
    next_month = (first_of_month + timedelta(days=32)).replace(day=1)
    first_of_month_str = first_of_month.isoformat()
    next_month_str = next_month.isoformat()
    today_str = today.isoformat()

    q = get_role_scoped_task_query(user)
    month_tasks = q.filter(
        Task.completed.is_(False),
        Task.status != "Completed",
        Task.due_date.is_not(None),
        Task.due_date >= first_of_month_str,
        Task.due_date < next_month_str
    ).all()

    due_dates = sorted(list({(t.due_date.isoformat() if hasattr(t.due_date, 'isoformat') else str(t.due_date)[:10]) for t in month_tasks if t.due_date}))

    upcoming_list = q.filter(
        Task.completed.is_(False),
        Task.status != "Completed",
        Task.due_date.is_not(None),
        Task.due_date >= today_str
    ).order_by(Task.due_date.asc()).limit(5).all()

    return jsonify(
        due_dates=due_dates,
        upcoming=[t.to_dict() for t in upcoming_list]
    ), 200
