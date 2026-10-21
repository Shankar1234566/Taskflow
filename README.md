# Taskflow Pro — Enterprise-Grade Productivity & Task Management Platform

**Taskflow Pro** is a modern, high-performance task management web application designed for professionals and teams. Built with a clean SaaS aesthetic, responsive design, light/dark themes, advanced task filtering, bulk actions, real-time productivity analytics, and an integrated **Admin Portal**.

---

## 🌟 Key Features

### 1. Advanced Task Management (Full CRUD+)
- **Extended Task Attributes**: Title, description, category/project, priority (`Critical`, `High`, `Medium`, `Low`), due date, due time, tags, and starred status.
- **Quick-Add Bar**: Instant task creation from the dashboard header with one keypress (`Enter`).
- **Detail View Drawer**: Comprehensive task inspection drawer showing timestamps, tags, priority, and quick actions.
- **Star & Prioritize**: Mark tasks as Important / Starred with instant visual indicators.
- **Task Duplication**: One-click cloning of repetitive tasks.
- **Bulk Actions**: Select multiple tasks with checkboxes to bulk-complete or bulk-delete.
- **Dual View Modes**: Switch between **List View** and **Grid / Kanban Cards View**.

### 2. Rich Productivity Views & Navigation
- **Collapsible Sidebar**: Sidebar with smooth transition, persisted state (`localStorage`), and responsive mobile drawer.
- **Light & Dark Theme Engine**: System-wide theme switcher with instant CSS token switching, persisted in `localStorage` and user profile.
- **Navigation Views**:
  - **Overview**: KPI metrics cards, SVG donut completion chart, upcoming tasks, AI recommendations, and recent activity.
  - **My Tasks**: Complete workspace with debounced search, category/priority/status filters, and custom sorting.
  - **Today**: Instant filter for tasks due today.
  - **Upcoming**: Tasks scheduled for future dates.
  - **Important / Starred**: Starred tasks archive.
  - **Completed**: Historical archive of completed tasks.
  - **Categories / Projects**: Workload progress bars and metrics grouped by category.
  - **Calendar**: Interactive monthly calendar with deadline dots and day inspector.
  - **Activity History**: Chronological audit trail of all task actions (created, updated, completed, starred, deleted).
  - **Settings & Profile**: Profile name customization, theme preference, and password change.
  - **Admin Portal**: Restricted administrative interface with system-wide analytics and user management directory.

### 3. Integrated Admin Portal (Role-Based Access)
- Restricted by `@admin_required` server-side authorization check (`403 Forbidden` for standard users).
- System-wide metrics: Total registered users, total system tasks, overall completion rate, and total activity volume.
- User management table: View all users, their task volume, and registered dates.
- Admin role management: Promote or demote users with safety protection against self-demotion and self-deletion.

### 4. Interactive Keyboard Shortcuts
- Press `/` to focus the search bar.
- Press `N` to open the Add Task modal.
- Press `T` to toggle light/dark theme.
- Press `[` to collapse or expand the sidebar.
- Press `Esc` to close any modal dialog or drawer.
- Press `?` to open the shortcuts cheat sheet.

---

## 🛠️ Technology Stack

- **Backend**: Python 3.10+ / Python 3.14, Flask 3.1+
- **Database**: SQLite with connection pragma foreign key enforcement (`PRAGMA foreign_keys=ON`)
- **ORM**: Flask-SQLAlchemy 3.1+
- **Security & Password Hashing**: Werkzeug Security Utilities (`generate_password_hash`, `check_password_hash`)
- **Authentication**: Secure Flask HTTP-only Sessions (`SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_SAMESITE="Lax"`)
- **Frontend**: Semantic HTML5, Vanilla CSS3 with CSS variables (Light/Dark themes), Vanilla ES6+ JavaScript
- **Testing**: pytest 9.1+ with in-memory SQLite isolation (38 test cases)

---

## 🚀 Windows Setup and Running Locally

Open **PowerShell** in the project directory:

```powershell
# 1. Activate the Python virtual environment
.\.venv\Scripts\Activate.ps1

# 2. Run automated tests (38 tests)
pytest -v

# 3. Start the application
python run.py
```

Open your browser to: **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## 📡 API Endpoint Documentation

All endpoints return JSON and use standard HTTP response codes (`200`, `201`, `400`, `401`, `403`, `404`, `409`).

### Authentication & Profile
- `POST /api/auth/register` (alias: `/signup`) — Register new user
- `POST /api/auth/login` — Authenticate and establish session
- `POST /api/auth/logout` — Terminate session
- `GET /api/auth/me` — Return current authenticated user profile
- `PUT /api/auth/profile` — Update user profile name and theme preference
- `PUT /api/auth/password` — Change password (requires current password validation)
- `POST /api/auth/google` — Google OAuth ID token verification

### Task Management
- `GET /api/tasks/` — List tasks for current user with search, filter, and sort
- `POST /api/tasks/` — Create a new task (supports `Critical`, `due_time`, `tags`, `is_starred`)
- `GET /api/tasks/<id>` — Get single task details
- `PUT /api/tasks/<id>` — Update task editable fields
- `PATCH /api/tasks/<id>/complete` — Toggle or set completion state
- `POST /api/tasks/<id>/star` — Toggle starred status
- `POST /api/tasks/<id>/duplicate` — Clone an existing task
- `DELETE /api/tasks/<id>` — Delete task
- `POST /api/tasks/bulk-complete` — Mark multiple tasks completed by IDs
- `POST /api/tasks/bulk-delete` — Delete multiple tasks by IDs
- `POST /api/tasks/reorder` — Update custom order index for tasks

### Dashboard & Analytics
- `GET /api/dashboard/` — Total, pending, completed, overdue, starred, and today counts
- `GET /api/dashboard/stats` — Full stats with 7-day trend analysis and category breakdowns
- `GET /api/dashboard/upcoming` — Calendar due dates and upcoming deadlines

### Activity History
- `GET /api/activity` — Get recent audit trail logs for the current user
- `DELETE /api/activity` — Clear activity history

### Admin Portal (`@admin_required`)
- `GET /api/admin/stats` — System-wide user and task metrics
- `GET /api/admin/users` — User directory with per-user task counts
- `POST /api/admin/users/<id>/toggle-admin` — Promote or demote user admin privileges
- `DELETE /api/admin/users/<id>` — Delete user and associated data

---

## 🧪 Automated Testing

Run the full pytest suite:
```powershell
pytest -v
```

**Test Suite Breakdown (38 Tests, 100% Passing)**:
- `tests/test_auth.py`: Registration, duplicate check, validation, login, wrong password, `/me`, logout, profile update, password change (12 tests).
- `tests/test_tasks.py`: Create, input validation, mass assignment prevention, filters, updates, completion toggle, deletion, cross-user isolation, critical priority, tags, star, duplicate, bulk actions (13 tests).
- `tests/test_dashboard.py`: Statistics calculation, user isolation, calendar upcoming, auth rejection (4 tests).
- `tests/test_admin.py`: Admin stats, users directory, 403 forbidden on regular users, role toggle, self-demotion prevention, user deletion, self-deletion prevention (7 tests).
- `tests/test_activity.py`: Audit trail logging on actions, clearing activity history (2 tests).

---

## 👥 GitHub Collaboration & Branching

All upgrade changes are staged on the feature branch:
```powershell
git checkout feature/flask-backend
git add .
git commit -m "feat: complete Taskflow Pro upgrade with admin portal, themes, and advanced task features"
git push -u origin feature/flask-backend
```
Then open a Pull Request targeting `main` on GitHub.
