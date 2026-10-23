from datetime import datetime, date, timezone
from . import db

def utc_now():
    return datetime.now(timezone.utc)

class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(50), nullable=False, default="Frontend")  # e.g., 'Frontend', 'Backend', 'Database', 'Design', 'Meetings'
    priority = db.Column(db.String(20), default="Medium", nullable=False)  # 'High', 'Medium', 'Low'
    status = db.Column(db.String(30), default="Pending", nullable=False)  # 'Pending', 'In Progress', 'In Review', 'Completed'
    due_date = db.Column(db.String(20), nullable=True)  # Format 'YYYY-MM-DD'
    due_time = db.Column(db.String(10), nullable=True)  # Format 'HH:MM'

    # Enterprise hierarchy foreign keys
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    blocked_by_id = db.Column(db.Integer, db.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True)

    # Proof of Work fields
    submission_notes = db.Column(db.Text, nullable=True)
    git_repo_link = db.Column(db.String(300), nullable=True)
    proof_file_path = db.Column(db.String(300), nullable=True)
    submitted_at = db.Column(db.DateTime, nullable=True)
    feedback_notes = db.Column(db.Text, nullable=True)

    # Additional productivity metadata
    tags = db.Column(db.String(255), default="", nullable=False)
    is_starred = db.Column(db.Boolean, default=False, nullable=False)
    completed = db.Column(db.Boolean, default=False, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    order_index = db.Column(db.Integer, default=0, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.Index("idx_team_status", "team_id", "status"),
        db.Index("idx_assignee_duedate", "assigned_to_id", "due_date"),
    )

    @property
    def display_status(self):
        """Computed task status including overdue state."""
        if self.completed or self.status == "Completed":
            return "Completed"
        if self.status == "In Review":
            return "In Review"
        if self.due_date:
            try:
                task_date = date.fromisoformat(str(self.due_date)[:10])
                if task_date < date.today():
                    return "Overdue"
            except (ValueError, TypeError):
                pass
        return self.status or "Pending"

    @property
    def is_overdue(self):
        if self.status == "Completed" or self.completed:
            return False
        if not self.due_date:
            return False
        try:
            task_date = date.fromisoformat(str(self.due_date)[:10])
            return task_date < date.today()
        except (ValueError, TypeError):
            return False

    @property
    def tags_list(self):
        if not self.tags:
            return []
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    def to_dict(self):
        assignee_name = None
        assignee_email = None
        if hasattr(self, "assignee") and self.assignee:
            assignee_name = self.assignee.username or self.assignee.name
            assignee_email = self.assignee.email

        creator_name = None
        if hasattr(self, "creator") and self.creator:
            creator_name = self.creator.username or self.creator.name

        team_name = None
        if hasattr(self, "team") and self.team:
            team_name = self.team.name

        effective_status = self.status or ("Completed" if self.completed else "Pending")
        computed_status = "Overdue" if self.is_overdue else effective_status

        return {
            "id": self.id,
            "title": self.title,
            "description": self.description or "",
            "category": self.category or "Frontend",
            "priority": self.priority or "Medium",
            "status": effective_status,
            "computed_status": computed_status,
            "is_overdue": self.is_overdue,
            "due_date": str(self.due_date) if self.due_date else None,
            "due_time": self.due_time,
            "team_id": self.team_id,
            "team_name": team_name,
            "created_by_id": self.created_by_id,
            "creator_name": creator_name,
            "assigned_to_id": self.assigned_to_id or self.user_id,
            "assignee_name": assignee_name,
            "assignee_email": assignee_email,
            "user_id": self.user_id or self.assigned_to_id,
            "blocked_by_id": self.blocked_by_id,
            "watcher_count": self.watcher_subscriptions.count() if hasattr(self, "watcher_subscriptions") and hasattr(self.watcher_subscriptions, "count") else 0,
            "submission_notes": self.submission_notes or "",
            "git_repo_link": self.git_repo_link or "",
            "proof_file_path": self.proof_file_path or "",
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "feedback_notes": self.feedback_notes or "",
            "tags": self.tags or "",
            "tags_list": self.tags_list,
            "is_starred": bool(self.is_starred),
            "completed": bool(self.completed or effective_status == "Completed"),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "order_index": self.order_index or 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
