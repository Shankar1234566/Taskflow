from datetime import datetime, date
from . import db

class Task(db.Model):
    __tablename__ = "tasks"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    category = db.Column(db.String(50), default="Work")
    priority = db.Column(db.String(10), default="Medium")  # High | Medium | Low
    due_date = db.Column(db.Date)
    completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def status(self):
        if self.completed:
            return "Completed"
        if self.due_date and self.due_date < date.today():
            return "Overdue"
        return "In Progress"

    def to_dict(self):
        return {"id": self.id, "title": self.title, "description": self.description,
                "category": self.category, "priority": self.priority,
                "due_date": self.due_date.isoformat() if self.due_date else None,
                "completed": self.completed, "status": self.status}
