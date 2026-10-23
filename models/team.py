from datetime import datetime, timezone
from . import db

def utc_now():
    return datetime.now(timezone.utc)

class Team(db.Model):
    __tablename__ = "teams"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)  # e.g., "Frontend Core", "Backend Systems", "QA / Infra"
    lead_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL", use_alter=True, name="fk_teams_lead_id"), nullable=True)
    default_bug_assignee_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL", use_alter=True, name="fk_teams_default_bug_assignee_id"), nullable=True)
    auto_routing_enabled = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    lead = db.relationship("User", foreign_keys=[lead_id], lazy=True)
    default_bug_assignee = db.relationship("User", foreign_keys=[default_bug_assignee_id], lazy=True)
    members = db.relationship("User", foreign_keys="User.team_id", backref="team", lazy=True)
    tasks = db.relationship("Task", foreign_keys="Task.team_id", backref="team", lazy=True)

    def to_dict(self):
        default_bug_assignee_name = None
        if self.default_bug_assignee:
            default_bug_assignee_name = self.default_bug_assignee.username or self.default_bug_assignee.name

        return {
            "id": self.id,
            "name": self.name,
            "lead_id": self.lead_id,
            "lead_name": (self.lead.username or self.lead.name) if self.lead else None,
            "default_bug_assignee_id": self.default_bug_assignee_id,
            "default_bug_assignee_name": default_bug_assignee_name,
            "auto_routing_enabled": bool(self.auto_routing_enabled),
            "member_count": len(self.members) if self.members else 0,
            "task_count": len(self.tasks) if self.tasks else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
