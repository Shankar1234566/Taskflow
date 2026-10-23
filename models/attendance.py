from datetime import datetime, timezone
from . import db

def utc_now():
    return datetime.now(timezone.utc)

class AttendanceRecord(db.Model):
    __tablename__ = "attendance_records"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date = db.Column(db.String(10), nullable=False, index=True)  # 'YYYY-MM-DD'
    check_in_time = db.Column(db.DateTime, nullable=True)
    check_out_time = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default="Present", nullable=False)  # 'Present', 'Half-Day', 'Absent'

    __table_args__ = (
        db.UniqueConstraint("user_id", "date", name="uq_user_attendance_date"),
    )

    user = db.relationship("User", foreign_keys=[user_id], backref=db.backref("attendance_records", lazy=True))

    @property
    def total_hours(self):
        """Calculate logged hours between check_in and check_out (or current time if still checked in)."""
        if not self.check_in_time:
            return 0.0
        end_time = self.check_out_time or datetime.utcnow()
        duration = (end_time - self.check_in_time).total_seconds()
        return max(0.0, round(duration / 3600.0, 2))

    def to_dict(self):
        user_name = self.user.username if self.user else "Unknown"
        initials = user_name[:2].upper() if user_name else "U"

        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_name": user_name,
            "user_initials": initials,
            "user_email": self.user.email if self.user else "",
            "date": self.date,
            "check_in_time": self.check_in_time.isoformat() if self.check_in_time else None,
            "check_out_time": self.check_out_time.isoformat() if self.check_out_time else None,
            "formatted_check_in": self.check_in_time.strftime("%I:%M %p") if self.check_in_time else None,
            "formatted_check_out": self.check_out_time.strftime("%I:%M %p") if self.check_out_time else None,
            "status": self.status,
            "total_hours": self.total_hours,
            "is_checked_in": bool(self.check_in_time and not self.check_out_time)
        }


class LeaveRequest(db.Model):
    __tablename__ = "leave_requests"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    leave_type = db.Column(db.String(30), nullable=False)  # 'Casual', 'Sick', 'Paid', 'Emergency'
    start_date = db.Column(db.String(10), nullable=False)  # 'YYYY-MM-DD'
    end_date = db.Column(db.String(10), nullable=False)    # 'YYYY-MM-DD'
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="Pending", nullable=False)  # 'Pending', 'Approved', 'Rejected'
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    review_comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    user = db.relationship("User", foreign_keys=[user_id], backref=db.backref("leave_requests", lazy=True))
    reviewer = db.relationship("User", foreign_keys=[reviewed_by_id], backref=db.backref("reviewed_leaves", lazy=True))
    team = db.relationship("Team", foreign_keys=[team_id], backref=db.backref("leave_requests", lazy=True))

    def to_dict(self):
        user_name = self.user.username if self.user else "Unknown"
        initials = user_name[:2].upper() if user_name else "U"
        reviewer_name = self.reviewer.username if self.reviewer else None

        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_name": user_name,
            "user_initials": initials,
            "user_email": self.user.email if self.user else "",
            "team_id": self.team_id,
            "team_name": self.team.name if self.team else None,
            "leave_type": self.leave_type,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "reason": self.reason,
            "status": self.status,
            "reviewed_by_id": self.reviewed_by_id,
            "reviewer_name": reviewer_name,
            "review_comment": self.review_comment,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "formatted_created_at": self.created_at.strftime("%b %d, %Y") if self.created_at else ""
        }
