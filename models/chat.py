from datetime import datetime, timezone
from . import db

def utc_now():
    return datetime.now(timezone.utc)

class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True, index=True)
    content = db.Column(db.Text, nullable=False)
    attachment_url = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    sender = db.relationship("User", foreign_keys=[sender_id], backref=db.backref("chat_messages", lazy=True))
    task = db.relationship("Task", foreign_keys=[task_id], backref=db.backref("chat_messages", lazy=True))
    team = db.relationship("Team", foreign_keys=[team_id], backref=db.backref("chat_messages", lazy=True))

    def to_dict(self):
        sender_name = self.sender.username if self.sender else "Unknown"
        initials = sender_name[:2].upper() if sender_name else "U"
        sender_role = self.sender.role if self.sender else "Member"
        task_title = self.task.title if self.task else None

        return {
            "id": self.id,
            "sender_id": self.sender_id,
            "sender_name": sender_name,
            "sender_initials": initials,
            "sender_role": sender_role,
            "team_id": self.team_id,
            "task_id": self.task_id,
            "task_title": task_title,
            "content": self.content,
            "attachment_url": self.attachment_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "formatted_time": self.created_at.strftime("%I:%M %p") if self.created_at else ""
        }
