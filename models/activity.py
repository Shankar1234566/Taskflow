from datetime import datetime, timezone
from . import db

def utc_now():
    return datetime.now(timezone.utc)

class ActivityLog(db.Model):
    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    action = db.Column(db.String(50), nullable=False)  # created, updated, completed, reopened, deleted, starred, unstarred, duplicated
    task_id = db.Column(db.Integer, nullable=True)
    task_title = db.Column(db.String(200), nullable=False)
    details = db.Column(db.String(255), default="", nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "action": self.action,
            "task_id": self.task_id,
            "task_title": self.task_title,
            "details": self.details,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
