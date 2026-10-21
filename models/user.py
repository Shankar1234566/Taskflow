from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from . import db, bcrypt

def utc_now():
    return datetime.now(timezone.utc)

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=True)  # nullable for OAuth / Google accounts
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    theme_preference = db.Column(db.String(20), default="light", nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    # Relationships
    tasks = db.relationship("Task", backref="user", cascade="all, delete-orphan", lazy=True)
    activities = db.relationship("ActivityLog", backref="user", cascade="all, delete-orphan", lazy=True)

    @property
    def username(self):
        """Compatibility property for frontend components expecting user.username."""
        return self.name

    @username.setter
    def username(self, value):
        self.name = value

    def set_password(self, password):
        """Hashes password using Werkzeug's secure hashing utility."""
        if not password:
            raise ValueError("Password cannot be empty.")
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verifies password using Werkzeug's check_password_hash, with bcrypt fallback."""
        if not self.password_hash or not password:
            return False
        # Legacy bcrypt support if existing database has $2b$ hashes
        if self.password_hash.startswith("$2b$") or self.password_hash.startswith("$2a$"):
            try:
                return bcrypt.check_password_hash(self.password_hash, password)
            except Exception:
                pass
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        """Returns safe user representation without sensitive fields."""
        return {
            "id": self.id,
            "name": self.name,
            "username": self.name,
            "email": self.email,
            "is_admin": bool(self.is_admin),
            "theme_preference": self.theme_preference or "light",
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
