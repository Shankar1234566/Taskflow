from datetime import datetime, timezone
from . import db

def utc_now():
    return datetime.now(timezone.utc)

class Team(db.Model):
    __tablename__ = "teams"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)  # Frontend, Backend, Mobile, QA
    lead_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL", use_alter=True, name="fk_teams_lead_id"), nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    # Relationships
    lead = db.relationship("User", foreign_keys=[lead_id], lazy=True)
    members = db.relationship("User", foreign_keys="User.team_id", backref="team", lazy=True)
    tasks = db.relationship("Task", foreign_keys="Task.team_id", backref="team", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "lead_id": self.lead_id,
            "lead_name": self.lead.name if self.lead else None,
            "member_count": len(self.members) if self.members else 0,
            "task_count": len(self.tasks) if self.tasks else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
