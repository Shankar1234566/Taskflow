# Taskflow Pro — Comprehensive REST API Reference

All requests and responses use JSON formatting (`Content-Type: application/json`).
Standard HTTP status codes indicate operation outcomes: `200 OK`, `201 Created`, `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, `404 Not Found`.

---

## 1. Authentication Endpoints

### `POST /api/auth/register`
Creates a new user account. The first registered user is automatically granted administrative privileges.
**Request Body**:
```json
{
  "name": "Jane Doe",
  "email": "jane@example.com",
  "password": "Password123!",
  "role": "Member",
  "team_id": 1
}
```
**Response (201 Created)**:
```json
{
  "message": "User registered successfully",
  "user": {
    "id": 1,
    "username": "Jane Doe",
    "email": "jane@example.com",
    "role": "Member",
    "is_admin": false
  }
}
```

### `POST /api/auth/login`
Authenticates user credentials and establishes an HTTP-only session cookie.
**Request Body**:
```json
{
  "email": "admin@taskflow.local",
  "password": "password123"
}
```

### `POST /api/auth/logout`
Destroys the current user session cookie.

### `GET /api/auth/me`
Returns current user profile information.

---

## 2. Task Management Endpoints

### `GET /api/tasks/`
Lists workspace tasks with multi-field filtering, sorting, and search.
**Query Parameters**:
- `status`: Filter by state (`Pending`, `In Progress`, `In Review`, `Completed`).
- `priority`: Filter by priority (`Critical`, `High`, `Medium`, `Low`).
- `category`: Filter by category.
- `search`: Keyword search in title and description.
- `team_id`: Filter by assigned squad.

### `POST /api/tasks/`
Creates a new task.
**Request Body**:
```json
{
  "title": "Migrate Database Composite Indexes",
  "description": "Benchmark query latency and add indexes.",
  "category": "Database",
  "priority": "High",
  "due_date": "2026-11-15",
  "assigned_to_id": 3
}
```

### `PATCH /api/tasks/<id>/complete`
Toggles task completion status and triggers activity audit logs.

### `POST /api/tasks/<id>/star`
Toggles starred/important status for fast retrieval.

### `DELETE /api/tasks/<id>`
Deletes a task. Restricted to creators, assignees, leads, and administrators.

---

## 3. Dashboard & Productivity Analytics

### `GET /api/dashboard/`
Returns summarized KPI counts:
- `total`: Total active deliverables.
- `completed`: Closed items.
- `in_progress`: Items under development.
- `in_review`: Deliverables pending lead signoff.
- `overdue`: Items whose due date has passed.
- `percent_complete`: Rounded progress ratio.

### `POST /api/assistant/query`
Productivity intelligence assistant synthesizing live SQLite task context into structured markdown summaries.
