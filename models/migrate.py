import sqlite3
import os

def apply_migrations(db_path):
    """
    Safely inspects existing SQLite database tables and adds newly introduced
    columns for Taskflow Enterprise without dropping tables or altering existing data.
    """
    if not os.path.exists(db_path):
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Create teams table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(50) NOT NULL UNIQUE,
                lead_id INTEGER,
                default_bug_assignee_id INTEGER,
                auto_routing_enabled BOOLEAN DEFAULT 1 NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(lead_id) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY(default_bug_assignee_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)

        # Check teams table columns
        cursor.execute("PRAGMA table_info(teams)")
        team_cols = {row[1] for row in cursor.fetchall()}
        if "default_bug_assignee_id" not in team_cols:
            cursor.execute("ALTER TABLE teams ADD COLUMN default_bug_assignee_id INTEGER REFERENCES users(id) ON DELETE SET NULL")
        if "auto_routing_enabled" not in team_cols:
            cursor.execute("ALTER TABLE teams ADD COLUMN auto_routing_enabled BOOLEAN DEFAULT 1 NOT NULL")

        # Create notifications and task_watchers tables if they do not exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipient_id INTEGER NOT NULL,
                sender_id INTEGER,
                task_id INTEGER,
                event_type VARCHAR(50) NOT NULL,
                title VARCHAR(120) NOT NULL,
                message TEXT NOT NULL,
                target_url VARCHAR(255),
                is_read BOOLEAN DEFAULT 0 NOT NULL,
                priority VARCHAR(20) DEFAULT 'Normal' NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(recipient_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(sender_id) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notif_recipient_read ON notifications(recipient_id, is_read)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notif_created ON notifications(created_at)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_watchers (
                task_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                subscribed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (task_id, user_id),
                FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Check users table columns
        cursor.execute("PRAGMA table_info(users)")
        user_cols = {row[1] for row in cursor.fetchall()}

        if "username" not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN username VARCHAR(80) DEFAULT 'User'")
            if "name" in user_cols:
                cursor.execute("UPDATE users SET username = name WHERE name IS NOT NULL")
        if "is_admin" not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0 NOT NULL")
        if "theme_preference" not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN theme_preference VARCHAR(20) DEFAULT 'light' NOT NULL")
        if "role" not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'Member' NOT NULL")
        if "team_id" not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN team_id INTEGER REFERENCES teams(id) ON DELETE SET NULL")

        # Check tasks table columns
        cursor.execute("PRAGMA table_info(tasks)")
        task_cols = {row[1] for row in cursor.fetchall()}

        if "due_time" not in task_cols:
            cursor.execute("ALTER TABLE tasks ADD COLUMN due_time VARCHAR(10)")
        if "tags" not in task_cols:
            cursor.execute("ALTER TABLE tasks ADD COLUMN tags VARCHAR(255) DEFAULT '' NOT NULL")
        if "is_starred" not in task_cols:
            cursor.execute("ALTER TABLE tasks ADD COLUMN is_starred BOOLEAN DEFAULT 0 NOT NULL")
        if "completed_at" not in task_cols:
            cursor.execute("ALTER TABLE tasks ADD COLUMN completed_at DATETIME")
        if "order_index" not in task_cols:
            cursor.execute("ALTER TABLE tasks ADD COLUMN order_index INTEGER DEFAULT 0 NOT NULL")

        # Multi-tier enterprise hierarchy columns
        if "status" not in task_cols:
            cursor.execute("ALTER TABLE tasks ADD COLUMN status VARCHAR(20) DEFAULT 'Pending' NOT NULL")
        if "team_id" not in task_cols:
            cursor.execute("ALTER TABLE tasks ADD COLUMN team_id INTEGER REFERENCES teams(id) ON DELETE SET NULL")
        if "created_by_id" not in task_cols:
            cursor.execute("ALTER TABLE tasks ADD COLUMN created_by_id INTEGER REFERENCES users(id) ON DELETE CASCADE")
        if "assigned_to_id" not in task_cols:
            cursor.execute("ALTER TABLE tasks ADD COLUMN assigned_to_id INTEGER REFERENCES users(id) ON DELETE SET NULL")
        if "blocked_by_id" not in task_cols:
            cursor.execute("ALTER TABLE tasks ADD COLUMN blocked_by_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL")

        # Proof of work columns
        if "submission_notes" not in task_cols:
            cursor.execute("ALTER TABLE tasks ADD COLUMN submission_notes TEXT")
        if "git_repo_link" not in task_cols:
            cursor.execute("ALTER TABLE tasks ADD COLUMN git_repo_link VARCHAR(500)")
        if "proof_file_path" not in task_cols:
            cursor.execute("ALTER TABLE tasks ADD COLUMN proof_file_path VARCHAR(500)")
        if "submitted_at" not in task_cols:
            cursor.execute("ALTER TABLE tasks ADD COLUMN submitted_at DATETIME")
        if "feedback_notes" not in task_cols:
            cursor.execute("ALTER TABLE tasks ADD COLUMN feedback_notes TEXT")

        # Sync existing status & assigned_to_id if null
        cursor.execute("UPDATE tasks SET status = 'Completed' WHERE completed = 1 AND (status IS NULL OR status = 'Pending')")
        cursor.execute("UPDATE tasks SET assigned_to_id = user_id WHERE assigned_to_id IS NULL AND user_id IS NOT NULL")
        cursor.execute("UPDATE tasks SET created_by_id = user_id WHERE created_by_id IS NULL AND user_id IS NOT NULL")

        # Seed initial squads if none exist
        cursor.execute("SELECT COUNT(*) FROM teams")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT OR IGNORE INTO teams (name) VALUES ('Frontend Squad')")
            cursor.execute("INSERT OR IGNORE INTO teams (name) VALUES ('Backend Squad')")
            cursor.execute("INSERT OR IGNORE INTO teams (name) VALUES ('Mobile Squad')")
            cursor.execute("INSERT OR IGNORE INTO teams (name) VALUES ('QA Squad')")

        # Create chat_messages table if it does not exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                team_id INTEGER NOT NULL,
                task_id INTEGER,
                content TEXT NOT NULL,
                attachment_url VARCHAR(255),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                FOREIGN KEY(sender_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE,
                FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_team_task ON chat_messages(team_id, task_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_created ON chat_messages(created_at)")

        # Create attendance_records table if it does not exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendance_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date VARCHAR(10) NOT NULL,
                check_in_time DATETIME,
                check_out_time DATETIME,
                status VARCHAR(20) DEFAULT 'Present' NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                CONSTRAINT uq_user_attendance_date UNIQUE(user_id, date)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_attendance_user_date ON attendance_records(user_id, date)")

        # Create leave_requests table if it does not exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS leave_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                team_id INTEGER NOT NULL,
                leave_type VARCHAR(30) NOT NULL,
                start_date VARCHAR(10) NOT NULL,
                end_date VARCHAR(10) NOT NULL,
                reason TEXT NOT NULL,
                status VARCHAR(20) DEFAULT 'Pending' NOT NULL,
                reviewed_by_id INTEGER,
                review_comment TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE,
                FOREIGN KEY(reviewed_by_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_leave_user_team ON leave_requests(user_id, team_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_leave_dates ON leave_requests(start_date, end_date)")

        # Create subtasks table if it does not exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subtasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                title VARCHAR(255) NOT NULL,
                is_completed BOOLEAN DEFAULT 0 NOT NULL,
                completed_at DATETIME,
                order_index INTEGER DEFAULT 0 NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_subtask_task ON subtasks(task_id)")

        # Verify subtask columns
        cursor.execute("PRAGMA table_info(subtasks)")
        subtask_cols = {row[1] for row in cursor.fetchall()}
        if "completed_at" not in subtask_cols:
            cursor.execute("ALTER TABLE subtasks ADD COLUMN completed_at DATETIME")
        if "order_index" not in subtask_cols:
            cursor.execute("ALTER TABLE subtasks ADD COLUMN order_index INTEGER DEFAULT 0 NOT NULL")

        conn.commit()
    except Exception as e:
        conn.rollback()
    finally:
        conn.close()
