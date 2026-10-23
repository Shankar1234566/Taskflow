from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from . import db

def utc_now():
    return datetime.now(timezone.utc)

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="Member", nullable=False)  # 'Admin', 'Lead', 'Member'
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="SET NULL", use_alter=True, name="fk_users_team_id"), nullable=True)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    theme_preference = db.Column(db.String(20), default="light", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    tasks = db.relationship("Task", foreign_keys="Task.user_id", backref="user", cascade="all, delete-orphan", lazy=True)
    assigned_tasks = db.relationship("Task", foreign_keys="Task.assigned_to_id", backref="assignee", lazy=True)
    created_tasks = db.relationship("Task", foreign_keys="Task.created_by_id", backref="creator", lazy=True)
    activities = db.relationship("ActivityLog", backref="user", cascade="all, delete-orphan", lazy=True)

    @property
    def name(self):
        """Compatibility property for templates/components expecting user.name."""
        return self.username

    @name.setter
    def name(self, value):
        self.username = value

    def set_password(self, password):
        """Hashes password using Werkzeug's secure hashing utility."""
        if not password:
            raise ValueError("Password cannot be empty.")
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verifies password using Werkzeug's check_password_hash."""
        if not self.password_hash or not password:
            return False
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        """Returns safe user representation without sensitive fields."""
        team_name = self.team.name if hasattr(self, "team") and self.team else None
        return {
            "id": self.id,
            "username": self.username,
            "name": self.username,
            "email": self.email,
            "role": self.role or ("Admin" if self.is_admin else "Member"),
            "is_admin": bool(self.is_admin or self.role == "Admin"),
            "team_id": self.team_id,
            "team_name": team_name,
            "theme_preference": self.theme_preference or "light",
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
