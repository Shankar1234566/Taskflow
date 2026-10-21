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
    category = db.Column(db.String(50), default="Work", nullable=False)
    priority = db.Column(db.String(10), default="Medium", nullable=False)  # Critical | High | Medium | Low
    due_date = db.Column(db.Date, nullable=True)
    due_time = db.Column(db.String(10), nullable=True)  # e.g. "17:00"
    tags = db.Column(db.String(255), default="", nullable=False)  # comma-separated tags
    is_starred = db.Column(db.Boolean, default=False, nullable=False)
    completed = db.Column(db.Boolean, default=False, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    order_index = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    @property
    def status(self):
        """Computed task status based on completion and due date."""
        if self.completed:
            return "Completed"
        if self.due_date and self.due_date < date.today():
            return "Overdue"
        return "In Progress"

    @property
    def tags_list(self):
        """Parse tags string into clean trimmed list."""
        if not self.tags:
            return []
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    def to_dict(self):
        """Serializes task fields for JSON responses."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "description": self.description or "",
            "category": self.category or "Work",
            "priority": self.priority or "Medium",
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "due_time": self.due_time or None,
            "tags": self.tags or "",
            "tags_list": self.tags_list,
            "is_starred": bool(self.is_starred),
            "completed": bool(self.completed),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "order_index": self.order_index or 0,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
