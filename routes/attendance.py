from datetime import datetime, date, timedelta, timezone
from flask import Blueprint, request, jsonify, session
from models import db, User, Team, AttendanceRecord, LeaveRequest
from utils.auth_decorators import login_required, role_required

attendance_bp = Blueprint("attendance", __name__)

def get_today_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

@attendance_bp.post("/check-in")
@login_required
def check_in():
    """
    Check-in endpoint: Logs current UTC time for today's date for current user.
    """
    user_id = session.get("user_id")
    user = db.session.get(User, user_id)
    if not user:
        return jsonify(error="Authentication required."), 401

    today_str = get_today_str()
    record = AttendanceRecord.query.filter_by(user_id=user.id, date=today_str).first()

    now_utc = datetime.utcnow()

    if record:
        if record.check_in_time and not record.check_out_time:
            return jsonify(
                record=record.to_dict(),
                message="You are already checked in for today."
            ), 200
        elif record.check_in_time and record.check_out_time:
            # Re-checkin / resuming work session
            record.check_out_time = None
            db.session.commit()
            return jsonify(
                record=record.to_dict(),
                is_checked_in=True,
                message="Resumed working session."
            ), 200
        else:
            record.check_in_time = now_utc
            record.status = "Present"
            db.session.commit()
            return jsonify(
                record=record.to_dict(),
                is_checked_in=True,
                message="Checked in successfully."
            ), 200

    new_record = AttendanceRecord(
        user_id=user.id,
        date=today_str,
        check_in_time=now_utc,
        status="Present"
    )
    db.session.add(new_record)
    db.session.commit()

    return jsonify(
        record=new_record.to_dict(),
        is_checked_in=True,
        message="Checked in successfully."
    ), 201

@attendance_bp.post("/check-out")
@login_required
def check_out():
    """
    Check-out endpoint: Updates checkout timestamp and calculates total logged hours.
    """
    user_id = session.get("user_id")
    user = db.session.get(User, user_id)
    if not user:
        return jsonify(error="Authentication required."), 401

    today_str = get_today_str()
    record = AttendanceRecord.query.filter_by(user_id=user.id, date=today_str).first()

    if not record or not record.check_in_time:
        return jsonify(error="Cannot check out without checking in first."), 400

    now_utc = datetime.utcnow()
    record.check_out_time = now_utc

    duration_seconds = (now_utc - record.check_in_time).total_seconds()
    hours = max(0.0, round(duration_seconds / 3600.0, 2))

    if hours < 4.5:
        record.status = "Half-Day"
    else:
        record.status = "Present"

    db.session.commit()

    return jsonify(
        record=record.to_dict(),
        is_checked_in=False,
        total_hours=hours,
        message="Checked out successfully."
    ), 200

@attendance_bp.get("/today")
@login_required
def get_today_status():
    """
    Returns current user's check-in status, daily & monthly metrics,
    and online teammates' status.
    """
    user_id = session.get("user_id")
    user = db.session.get(User, user_id)
    if not user:
        return jsonify(error="Authentication required."), 401

    today_str = get_today_str()
    current_record = AttendanceRecord.query.filter_by(user_id=user.id, date=today_str).first()

    # Monthly metrics
    current_month_prefix = today_str[:7]  # 'YYYY-MM'
    monthly_records = AttendanceRecord.query.filter(
        AttendanceRecord.user_id == user.id,
        AttendanceRecord.date.like(f"{current_month_prefix}%")
    ).all()

    total_monthly_hours = sum(r.total_hours for r in monthly_records)
    working_days_present = len([r for r in monthly_records if r.check_in_time])

    # Approved leave count this month
    approved_leaves_count = LeaveRequest.query.filter(
        LeaveRequest.user_id == user.id,
        LeaveRequest.status == "Approved",
        LeaveRequest.start_date.like(f"{current_month_prefix}%")
    ).count()

    # Leave balance (standard allocation: 20 per year, approx 2 per month)
    leave_balance = max(0, 18 - approved_leaves_count)

    # Teammates in same squad
    teammates = []
    if user.team_id:
        squad_users = User.query.filter_by(team_id=user.team_id).all()
        for member in squad_users:
            if member.id == user.id:
                continue
            rec = AttendanceRecord.query.filter_by(user_id=member.id, date=today_str).first()
            is_checked_in = bool(rec and rec.check_in_time and not rec.check_out_time)
            is_checked_out = bool(rec and rec.check_out_time)

            # Check if member is on approved leave today
            on_leave = LeaveRequest.query.filter(
                LeaveRequest.user_id == member.id,
                LeaveRequest.status == "Approved",
                LeaveRequest.start_date <= today_str,
                LeaveRequest.end_date >= today_str
            ).first()

            teammates.append({
                "id": member.id,
                "name": member.username,
                "initials": member.username[:2].upper(),
                "role": member.role,
                "is_checked_in": is_checked_in,
                "is_checked_out": is_checked_out,
                "total_hours": rec.total_hours if rec else 0.0,
                "on_leave": bool(on_leave),
                "leave_type": on_leave.leave_type if on_leave else None
            })

    return jsonify(
        current_record=current_record.to_dict() if current_record else None,
        is_checked_in=bool(current_record and current_record.check_in_time and not current_record.check_out_time),
        metrics={
            "today_hours": current_record.total_hours if current_record else 0.0,
            "monthly_hours": round(total_monthly_hours, 2),
            "working_days": working_days_present,
            "approved_leaves": approved_leaves_count,
            "leave_balance": leave_balance
        },
        teammates=teammates
    ), 200

@attendance_bp.get("/presence")
@login_required
def get_presence_map():
    """
    Returns visual presence mapping for all team users:
    - is_checked_in (green active dot)
    - on_leave (amber calendar badge)
    """
    today_str = get_today_str()
    records = AttendanceRecord.query.filter_by(date=today_str).all()
    checked_in_user_ids = {r.user_id for r in records if r.check_in_time and not r.check_out_time}

    # Active approved leaves today
    leaves = LeaveRequest.query.filter(
        LeaveRequest.status == "Approved",
        LeaveRequest.start_date <= today_str,
        LeaveRequest.end_date >= today_str
    ).all()
    on_leave_map = {l.user_id: l.leave_type for l in leaves}

    presence = {}
    users = User.query.all()
    for u in users:
        presence[u.id] = {
            "is_checked_in": u.id in checked_in_user_ids,
            "on_leave": u.id in on_leave_map,
            "leave_type": on_leave_map.get(u.id)
        }

    return jsonify(presence=presence), 200

leaves_bp = Blueprint("leaves", __name__)

# ==============================================================================
# LEAVE MANAGEMENT ENDPOINTS
# ==============================================================================

@leaves_bp.post("/apply")
@attendance_bp.post("/leaves/apply")
@attendance_bp.post("/leave/apply")
@login_required
def apply_leave():
    """
    Employee submits leave request with date range and reason.
    POST /api/leaves/apply or POST /api/attendance/leaves/apply
    """
    user_id = session.get("user_id")
    user = db.session.get(User, user_id)
    if not user:
        return jsonify(error="Authentication required."), 401

    data = request.get_json(silent=True) or {}
    leave_type = (data.get("leave_type") or "").strip()
    start_date = (data.get("start_date") or "").strip()
    end_date = (data.get("end_date") or "").strip()
    reason = (data.get("reason") or "").strip()

    valid_types = ("Casual", "Sick", "Paid", "Emergency")
    if leave_type not in valid_types:
        return jsonify(error=f"Invalid leave type. Choose from: {', '.join(valid_types)}"), 400

    if not start_date or not end_date:
        return jsonify(error="Start date and end date are required."), 400

    try:
        s_date = date.fromisoformat(start_date)
        e_date = date.fromisoformat(end_date)
        if s_date > e_date:
            return jsonify(error="Start date cannot be after end date."), 400
    except ValueError:
        return jsonify(error="Invalid date format. Use YYYY-MM-DD."), 400

    if not reason:
        return jsonify(error="Reason for leave is required."), 400

    team_id = user.team_id
    if not team_id:
        first_team = Team.query.first()
        team_id = first_team.id if first_team else 1

    leave = LeaveRequest(
        user_id=user.id,
        team_id=team_id,
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        reason=reason,
        status="Pending"
    )
    db.session.add(leave)
    db.session.commit()

    return jsonify(leave=leave.to_dict(), message="Leave request submitted successfully."), 201

@leaves_bp.get("")
@leaves_bp.get("/")
@attendance_bp.get("/leaves")
@attendance_bp.get("/leave")
@login_required
def get_leaves():
    """
    Fetch leave requests based on user role:
    - If Employee: Returns their own leave applications and history.
    - If Team Lead: Returns all pending and active leave requests for their team members, plus own leaves.
    - If Admin: Returns all leave requests across the company.
    """
    user_id = session.get("user_id")
    user = db.session.get(User, user_id)
    if not user:
        return jsonify(error="Authentication required."), 401

    if user.role == "Admin" or user.is_admin:
        leaves = LeaveRequest.query.order_by(LeaveRequest.created_at.desc()).all()
    elif user.role == "Lead":
        if user.team_id:
            leaves = LeaveRequest.query.filter(
                db.or_(
                    LeaveRequest.team_id == user.team_id,
                    LeaveRequest.user_id == user.id
                )
            ).order_by(LeaveRequest.created_at.desc()).all()
        else:
            leaves = LeaveRequest.query.filter_by(user_id=user.id).order_by(LeaveRequest.created_at.desc()).all()
    else:
        # Member / Employee
        leaves = LeaveRequest.query.filter_by(user_id=user.id).order_by(LeaveRequest.created_at.desc()).all()

    return jsonify(leaves=[l.to_dict() for l in leaves]), 200

@leaves_bp.patch("/<int:leave_id>/action")
@attendance_bp.patch("/leaves/<int:leave_id>/action")
@attendance_bp.patch("/leave/<int:leave_id>/action")
@login_required
def action_leave(leave_id):
    """
    Team Lead approves or rejects leave request with review comments.
    PATCH /api/leaves/<id>/action
    """
    user_id = session.get("user_id")
    user = db.session.get(User, user_id)
    if not user:
        return jsonify(error="Authentication required."), 401

    is_lead_or_admin = user.role in ("Lead", "Admin") or user.is_admin
    if not is_lead_or_admin:
        return jsonify(error="Forbidden. Team Lead or Admin approval authority required."), 403

    leave = db.session.get(LeaveRequest, leave_id)
    if not leave:
        return jsonify(error="Leave request not found."), 404

    # Lead can only review requests from their own squad
    if user.role == "Lead" and not user.is_admin:
        if user.team_id and leave.team_id != user.team_id:
            return jsonify(error="Forbidden. You can only review leave requests for your designated squad."), 403

    data = request.get_json(silent=True) or {}
    action = (data.get("action") or "").strip().lower()
    comment = (data.get("comment") or "").strip()

    if action not in ("approve", "reject"):
        return jsonify(error="Action must be 'approve' or 'reject'."), 400

    leave.status = "Approved" if action == "approve" else "Rejected"
    leave.reviewed_by_id = user.id
    leave.review_comment = comment
    db.session.commit()

    return jsonify(
        leave=leave.to_dict(),
        message=f"Leave request {leave.status.lower()} successfully."
    ), 200
