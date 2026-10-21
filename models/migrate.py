import sqlite3
import os
from flask import current_app

def apply_migrations(db_path):
    """
    Safely inspects existing SQLite database tables and adds any newly introduced
    columns for Taskflow Pro without dropping tables or altering existing data.
    """
    if not os.path.exists(db_path):
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check users table columns
        cursor.execute("PRAGMA table_info(users)")
        user_cols = {row[1] for row in cursor.fetchall()}

        if "is_admin" not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0 NOT NULL")
        if "theme_preference" not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN theme_preference VARCHAR(20) DEFAULT 'light' NOT NULL")

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

        conn.commit()
    except Exception as e:
        # Non-fatal if table doesn't exist yet (db.create_all will create it)
        conn.rollback()
    finally:
        conn.close()
