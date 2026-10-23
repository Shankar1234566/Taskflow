from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from sqlalchemy import event
from sqlalchemy.engine import Engine
import sqlite3

db = SQLAlchemy()
bcrypt = Bcrypt()

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enforce SQLite foreign key constraints on every database connection."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

from .team import Team  # noqa: E402
from .user import User  # noqa: E402
from .task import Task  # noqa: E402
from .activity import ActivityLog  # noqa: E402
from .notification import Notification, TaskWatcher  # noqa: E402
from .chat import ChatMessage  # noqa: E402
from .attendance import AttendanceRecord, LeaveRequest  # noqa: E402
