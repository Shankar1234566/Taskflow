from datetime import datetime, timezone
from . import db

def utc_now():
    return datetime.now(timezone.utc)

class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Event Types: 'TASK_ASSIGNED', 'STATUS_CHANGED', 'BUG_ROUTED', 'BLOCKER_RESOLVED', 'REVIEW_REQUESTED', 'FEEDBACK_SUBMITTED', 'HIGH_PRIORITY_BUG'
    event_type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    target_url = db.Column(db.String(255), nullable=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    priority = db.Column(db.String(20), default="Normal", nullable=False)  # 'Normal', 'Urgent'
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    recipient = db.relationship("User", foreign_keys=[recipient_id], backref=db.backref("notifications", cascade="all, delete-orphan", lazy="dynamic"))
    sender = db.relationship("User", foreign_keys=[sender_id], lazy=True)
    task = db.relationship("Task", foreign_keys=[task_id], backref=db.backref("notifications", cascade="all, delete-orphan", lazy="dynamic"))

    __table_args__ = (
        db.Index("idx_notif_recipient_read", "recipient_id", "is_read"),
        db.Index("idx_notif_created", "created_at"),
    )

    def to_dict(self):
        sender_name = "System"
        if self.sender:
            sender_name = self.sender.username or self.sender.name

        task_title = self.task.title if self.task else None

        return {
            "id": self.id,
            "recipient_id": self.recipient_id,
            "sender_id": self.sender_id,
            "sender_name": sender_name,
            "task_id": self.task_id,
            "task_title": task_title,
            "event_type": self.event_type,
            "title": self.title,
            "message": self.message,
            "target_url": self.target_url or (f"#task-{self.task_id}" if self.task_id else ""),
            "is_read": bool(self.is_read),
            "priority": self.priority,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "time_ago": self._calculate_time_ago()
        }

    def _calculate_time_ago(self):
        """Helper to compute human-friendly relative time string."""
        if not self.created_at:
            return "just now"
        delta = datetime.utcnow() - self.created_at
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return "just now"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        if days < 7:
            return f"{days}d ago"
        return self.created_at.strftime("%b %d")


class TaskWatcher(db.Model):
    __tablename__ = "task_watchers"

    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    subscribed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    watcher = db.relationship("User", foreign_keys=[user_id], backref=db.backref("watched_subscriptions", cascade="all, delete-orphan", lazy="dynamic"))
    watched_task = db.relationship("Task", foreign_keys=[task_id], backref=db.backref("watcher_subscriptions", cascade="all, delete-orphan", lazy="dynamic"))

    def to_dict(self):
        return {
            "task_id": self.task_id,
            "user_id": self.user_id,
            "subscribed_at": self.subscribed_at.isoformat() if self.subscribed_at else None
        }
