from datetime import datetime, date, timezone
from . import db

def utc_now():
    return datetime.now(timezone.utc)

class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="", nullable=False)
    category = db.Column(db.String(50), default="Frontend", nullable=False)  # Frontend, Backend, Bug, QA, Docs
    priority = db.Column(db.String(10), default="Medium", nullable=False)  # Critical | High | Medium | Low
    status = db.Column(db.String(20), default="Pending", nullable=False)  # Pending | In Progress | In Review | Completed
    due_date = db.Column(db.Date, nullable=True)
    due_time = db.Column(db.String(10), nullable=True)  # e.g. "17:00"
    tags = db.Column(db.String(255), default="", nullable=False)  # comma-separated tags
    is_starred = db.Column(db.Boolean, default=False, nullable=False)
    completed = db.Column(db.Boolean, default=False, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    order_index = db.Column(db.Integer, default=0, nullable=False)

    # Enterprise hierarchy foreign keys
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Proof of work submission columns
    submission_notes = db.Column(db.Text, nullable=True)
    git_repo_link = db.Column(db.String(500), nullable=True)
    proof_file_path = db.Column(db.String(500), nullable=True)
    submitted_at = db.Column(db.DateTime, nullable=True)
    feedback_notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    @property
    def display_status(self):
        """Computed task status including overdue state."""
        if self.completed or self.status == "Completed":
            return "Completed"
        if self.status == "In Review":
            return "In Review"
        if self.due_date and self.due_date < date.today():
            return "Overdue"
        return self.status or "Pending"

    @property
    def tags_list(self):
        """Parse tags string into clean trimmed list."""
        if not self.tags:
            return []
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    def to_dict(self):
        """Serializes task fields for JSON responses."""
        assignee_name = None
        assignee_email = None
        if hasattr(self, "assignee") and self.assignee:
            assignee_name = self.assignee.name
            assignee_email = self.assignee.email

        creator_name = None
        if hasattr(self, "creator") and self.creator:
            creator_name = self.creator.name

        team_name = None
        if hasattr(self, "team") and self.team:
            team_name = self.team.name

        effective_status = self.status or ("Completed" if self.completed else "Pending")
        # For legacy compatibility, if overdue
        if not self.completed and effective_status not in ("In Review", "Completed"):
            if self.due_date and self.due_date < date.today():
                computed_status = "Overdue"
            else:
                computed_status = effective_status
        else:
            computed_status = effective_status

        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "description": self.description or "",
            "category": self.category or "Frontend",
            "priority": self.priority or "Medium",
            "status": effective_status,
            "computed_status": computed_status,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "due_time": self.due_time or None,
            "tags": self.tags or "",
            "tags_list": self.tags_list,
            "is_starred": bool(self.is_starred),
            "completed": bool(self.completed or effective_status == "Completed"),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "order_index": self.order_index or 0,
            "team_id": self.team_id,
            "team_name": team_name,
            "created_by_id": self.created_by_id,
            "creator_name": creator_name,
            "assigned_to_id": self.assigned_to_id or self.user_id,
            "assignee_name": assignee_name or (self.user.name if hasattr(self, "user") and self.user else None),
            "assignee_email": assignee_email,
            "submission_notes": self.submission_notes or "",
            "git_repo_link": self.git_repo_link or "",
            "proof_file_path": self.proof_file_path or "",
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "feedback_notes": self.feedback_notes or "",
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
