# Taskflow Pro — Architecture & Engineering Blueprint

## 1. System Overview & Domain Model
Taskflow Pro is built upon clean architecture principles, separating the presentation layer (Single Page Application UI) from domain service logic and transactional persistence.

```
+-------------------------------------------------------------+
|                      Frontend Client                        |
|   HTML5 + Vanilla ES6 Modules + CSS Custom Properties Engine|
+-------------------------------------------------------------+
                              | REST JSON API / Session Cookie
                              v
+-------------------------------------------------------------+
|                     Flask API Gateway                       |
|   Role-Based Authorization Decorators (@login_required,     |
|   @admin_required) + Input Validation Layer                 |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                     Services Domain Layer                   |
|   * Workflow Orchestration Engine (DAG & State Machine)     |
|   * Analytics & Sprint Forecasting (Monte Carlo Simulation) |
|   * Multi-Channel Notification Dispatcher                   |
|   * RBAC / ABAC Security Policy Engine                      |
|   * Cryptographic Audit Logger & Compliance Scanner         |
|   * External Integrations (GitHub, GitLab, Jira, Slack)     |
+-------------------------------------------------------------+
                              | SQLAlchemy ORM
                              v
+-------------------------------------------------------------+
|                    Storage Engine                           |
|   SQLite with WAL Mode & PRAGMA foreign_keys = ON           |
+-------------------------------------------------------------+
```

## 2. Relational Database Design
The SQLite schema implements strict foreign key cascades and integrity constraints:
- `users`: Authenticated user accounts with bcrypt password hashes and role archetypes (`Admin`, `Lead`, `Member`).
- `teams`: Organizational departments and squads with designated team leads.
- `tasks`: Work items with priority, status, category, due dates, proof of work links, and reviewer feedback.
- `activity_logs`: Immutable chronological audit logs recording state transitions and user actions.

## 3. Workflow State Machine Lifecycle
Tasks transition through explicit verified stages:
1. `BACKLOG`: Initial backlog triage.
2. `TODO`: Scheduled sprint commitments.
3. `IN_PROGRESS`: Developer active execution.
4. `BLOCKED`: Roadblocks escalated with required blocker reasons.
5. `IN_REVIEW`: Deliverable submitted with pull request or proof notes.
6. `COMPLETED`: Approved by team lead or administrator.
7. `ARCHIVED`: Closed milestone retention.

## 4. Security & Isolation Controls
- HTTP-Only session cookies with `SameSite=Lax` prevent XSS token theft.
- Cross-user data isolation ensures regular members only modify tasks assigned to or created by them.
- Administrative routes (`/api/admin/*`) enforce strict role authorization checks with immediate 403 Forbidden responses.
