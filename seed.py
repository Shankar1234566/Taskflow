import os
from datetime import date, datetime, timedelta, timezone
from app import create_app
from models import db, User, Team, Task

def seed_database():
    app = create_app()
    with app.app_context():
        print("[*] Seeding Taskflow enterprise database...")
        db.drop_all()
        db.create_all()

        # 1. Create Teams
        backend_team = Team(name="Backend Systems")
        frontend_team = Team(name="Frontend Core")
        db.session.add_all([backend_team, frontend_team])
        db.session.commit()

        # 2. Create Users
        admin_user = User(
            username="System Administrator",
            email="admin@taskflow.local",
            role="Admin",
            is_admin=True,
            team_id=None
        )
        admin_user.set_password("password123")

        lead_backend_user = User(
            username="Sarah Jenkins",
            email="lead_backend@taskflow.local",
            role="Lead",
            is_admin=False,
            team_id=backend_team.id
        )
        lead_backend_user.set_password("password123")

        dev_backend_user = User(
            username="Alex Rivera",
            email="dev_backend@taskflow.local",
            role="Member",
            is_admin=False,
            team_id=backend_team.id
        )
        dev_backend_user.set_password("password123")

        dev_frontend_user = User(
            username="Elena Rostova",
            email="dev_frontend@taskflow.local",
            role="Member",
            is_admin=False,
            team_id=frontend_team.id
        )
        dev_frontend_user.set_password("password123")

        db.session.add_all([admin_user, lead_backend_user, dev_backend_user, dev_frontend_user])
        db.session.commit()

        # Update squad lead
        backend_team.lead_id = lead_backend_user.id
        db.session.commit()

        # 3. Create 10 Realistic Tasks
        today = date.today()
        d_minus_5 = (today - timedelta(days=5)).isoformat()
        d_minus_3 = (today - timedelta(days=3)).isoformat()
        d_today = today.isoformat()
        d_plus_2 = (today + timedelta(days=2)).isoformat()
        d_plus_4 = (today + timedelta(days=4)).isoformat()
        d_plus_7 = (today + timedelta(days=7)).isoformat()

        tasks = [
            # 1. Overdue Task 1
            Task(
                title="Legacy API Deprecation Migration",
                description="Migrate all v1 authorization headers and obsolete payload schemas to unified JWT handlers.",
                category="Backend",
                priority="Critical",
                status="In Progress",
                due_date=d_minus_5,
                team_id=backend_team.id,
                created_by_id=lead_backend_user.id,
                assigned_to_id=dev_backend_user.id,
                user_id=dev_backend_user.id,
                tags="migration, security, v1-sunset"
            ),
            # 2. Overdue Task 2
            Task(
                title="Fix Responsive Header Layout Overflow",
                description="Fix viewport clipping on tablet devices when top navigation elements wrap unexpectedly.",
                category="Frontend",
                priority="High",
                status="Pending",
                due_date=d_minus_3,
                team_id=frontend_team.id,
                created_by_id=admin_user.id,
                assigned_to_id=dev_frontend_user.id,
                user_id=dev_frontend_user.id,
                tags="css, mobile, layout"
            ),
            # 3. In Review Task 1
            Task(
                title="REST API Rate Limiting Middleware",
                description="Implement sliding window token bucket rate limiting using SQLite connection locking with fallback.",
                category="Backend",
                priority="High",
                status="In Review",
                due_date=d_today,
                team_id=backend_team.id,
                created_by_id=lead_backend_user.id,
                assigned_to_id=dev_backend_user.id,
                user_id=dev_backend_user.id,
                submission_notes="Implemented sliding window middleware under utils/rate_limit.py. Unit tests passing at 98% coverage.",
                git_repo_link="https://github.com/enterprise/taskflow/pull/142",
                submitted_at=datetime.now(timezone.utc) - timedelta(hours=3),
                tags="api, security, middleware"
            ),
            # 4. In Review Task 2
            Task(
                title="Auth Session Token Invalidation Guard",
                description="Add explicit cookie domain checks and prevent stale bearer tokens from accessing protected views.",
                category="Frontend",
                priority="High",
                status="In Review",
                due_date=d_today,
                team_id=frontend_team.id,
                created_by_id=admin_user.id,
                assigned_to_id=dev_frontend_user.id,
                user_id=dev_frontend_user.id,
                submission_notes="Integrated fetch interceptor to catch 401s and automatically trigger clean session logout.",
                git_repo_link="https://github.com/enterprise/taskflow/pull/144",
                submitted_at=datetime.now(timezone.utc) - timedelta(hours=1),
                tags="auth, session, frontend"
            ),
            # 5. In Progress Task 1
            Task(
                title="Database Composite Index Optimization",
                description="Benchmark query latency and add composite indexes on (team_id, status) and (assigned_to_id, due_date).",
                category="Database",
                priority="High",
                status="In Progress",
                due_date=d_plus_2,
                team_id=backend_team.id,
                created_by_id=lead_backend_user.id,
                assigned_to_id=dev_backend_user.id,
                user_id=dev_backend_user.id,
                tags="db, indexing, performance"
            ),
            # 6. In Progress Task 2
            Task(
                title="Interactive SVG Donut Progress Chart",
                description="Build smooth animated SVG stroke-dasharray donut indicator showing completion ratios.",
                category="Frontend",
                priority="Medium",
                status="In Progress",
                due_date=d_plus_4,
                team_id=frontend_team.id,
                created_by_id=admin_user.id,
                assigned_to_id=dev_frontend_user.id,
                user_id=dev_frontend_user.id,
                tags="svg, charts, ui"
            ),
            # 7. Pending Task 1
            Task(
                title="Implement Redis Caching Layer for Dashboard",
                description="Evaluate TTL cache strategies for system wide metric counts under heavy concurrent load.",
                category="Backend",
                priority="Medium",
                status="Pending",
                due_date=d_plus_7,
                team_id=backend_team.id,
                created_by_id=lead_backend_user.id,
                assigned_to_id=dev_backend_user.id,
                user_id=dev_backend_user.id,
                tags="cache, redis, scalability"
            ),
            # 8. Pending Task 2
            Task(
                title="Sprint Retrospective Planning & Team Sync",
                description="Organize quarterly milestone review and align backlog priorities across squad leads.",
                category="Meetings",
                priority="Low",
                status="Pending",
                due_date=d_plus_7,
                team_id=frontend_team.id,
                created_by_id=admin_user.id,
                assigned_to_id=dev_frontend_user.id,
                user_id=dev_frontend_user.id,
                tags="sprint, planning"
            ),
            # 9. Completed Task 1
            Task(
                title="Bootstrap Enterprise RBAC Models",
                description="Define Team, User, Task entities and establish cascade constraints in SQLite.",
                category="Database",
                priority="High",
                status="Completed",
                completed=True,
                completed_at=datetime.now(timezone.utc) - timedelta(days=2),
                due_date=d_minus_3,
                team_id=backend_team.id,
                created_by_id=admin_user.id,
                assigned_to_id=dev_backend_user.id,
                user_id=dev_backend_user.id,
                submission_notes="Entity models generated with strict foreign key constraints and bcrypt/werkzeug password hashing.",
                git_repo_link="https://github.com/enterprise/taskflow/pull/130",
                feedback_notes="Excellent schema structure. Approved without revisions.",
                tags="orm, models, rbac"
            ),
            # 10. Completed Task 2
            Task(
                title="Design System Light-Mode Tokens",
                description="Harmonize HSL color palette, soft shadows, typography scales, and CSS variables.",
                category="Design",
                priority="Medium",
                status="Completed",
                completed=True,
                completed_at=datetime.now(timezone.utc) - timedelta(days=1),
                due_date=d_minus_3,
                team_id=frontend_team.id,
                created_by_id=admin_user.id,
                assigned_to_id=dev_frontend_user.id,
                user_id=dev_frontend_user.id,
                submission_notes="Tokens configured for #F8F9FA background, #2E7D32 forest green, and modern Inter typography.",
                git_repo_link="https://github.com/enterprise/taskflow/pull/135",
                feedback_notes="Visual look and feel meets modern enterprise standards.",
                tags="css, design-system"
            )
        ]

        db.session.add_all(tasks)
        db.session.commit()

        print("[OK] Database successfully seeded with:")
        print("   - 2 Teams ('Backend Systems', 'Frontend Core')")
        print("   - 4 Users:")
        print("     * admin@taskflow.local (Admin)")
        print("     * lead_backend@taskflow.local (Lead)")
        print("     * dev_backend@taskflow.local (Member)")
        print("     * dev_frontend@taskflow.local (Member)")
        print("   - 10 Realistic Tasks (2 Overdue, 2 In Review, 2 In Progress, 2 Pending, 2 Completed)")

if __name__ == "__main__":
    seed_database()
