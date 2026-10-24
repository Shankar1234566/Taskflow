from datetime import datetime, timezone
from . import db

def utc_now():
    return datetime.now(timezone.utc)

class Subtask(db.Model):
    """
    Subtask / Acceptance Criteria entity for granular deliverable decomposition.
    Cascades on parent task deletion and tracks individual completion state.
    """
    __tablename__ = "subtasks"

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    is_completed = db.Column(db.Boolean, default=False, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    order_index = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    task = db.relationship("Task", back_populates="subtasks")

    def to_dict(self):
        """Serialize Subtask model to clean JSON dictionary."""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "title": self.title,
            "is_completed": bool(self.is_completed),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "order_index": self.order_index or 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
