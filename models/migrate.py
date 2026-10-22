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
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(lead_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)

        # Check users table columns
        cursor.execute("PRAGMA table_info(users)")
        user_cols = {row[1] for row in cursor.fetchall()}

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

        # Ensure first user is Admin
        cursor.execute("UPDATE users SET role = 'Admin' WHERE is_admin = 1 AND (role IS NULL OR role = 'Member')")

        conn.commit()
    except Exception as e:
        conn.rollback()
    finally:
        conn.close()
