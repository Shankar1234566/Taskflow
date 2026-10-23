"""
Synthetic Dataset Generator for Enterprise Benchmarks and Load Testing.
Generates realistic engineers, squads, projects, sprint cadences, and deliverables.
"""
from datetime import date, datetime, timedelta, timezone
import random
from typing import Dict, List, Any


class SyntheticDataEngine:
    """Generates synthetic enterprise workflows and ticket collections."""

    CATEGORIES = ["Backend", "Frontend", "Database", "Security", "DevOps", "Design", "Quality Assurance", "Architecture"]
    PRIORITIES = ["Critical", "High", "Medium", "Low"]
    STATUSES = ["Pending", "In Progress", "In Review", "Completed", "Blocked"]

    TITLES = [
        "Implement Multi-Region Database Replica Failover",
        "Refactor JWT Session Cookie Invalidation Interceptor",
        "Author Microservice GraphQL Schema Federation",
        "Migrate Redis Cache Serialization to MessagePack",
        "Resolve CSS Viewport Layout Clipping on Retina Displays",
        "Integrate OAuth2 PKCE Authorization Code Grant",
        "Optimize Composite Index for (team_id, status, due_date)",
        "Audit Open Source Dependencies for CVE Vulnerabilities",
        "Construct Interactive Canvas Burndown Velocity Chart",
        "Deploy Automated Container Security Scanning in CI Pipeline",
        "Refactor Monolithic Flask Blueprint Module Hierarchy",
        "Write Comprehensive Pytest Integration Test Fixtures",
        "Configure Prometheus Metrics Exporter and Grafana Dashboard",
        "Standardize HTTP 429 Sliding Window Rate Limiting",
        "Implement Real-Time WebSocket Notification Dispatcher",
        "Validate Foreign Key Cascades across SQLite Tables",
        "Build Drag-and-Drop Kanban Task Board with Swimlanes",
        "Enforce Strict Content Security Policy (CSP) Headers",
        "Benchmark Database Connection Pool Contention",
        "Design Resilient Outgoing Webhook Retry Backoff Engine"
    ]

    @classmethod
    def generate_synthetic_workload(cls, count: int = 50, seed: int = 101) -> List[Dict[str, Any]]:
        rng = random.Random(seed)
        tasks = []
        today = date.today()

        for i in range(1, count + 1):
            offset_days = rng.randint(-14, 21)
            due = (today + timedelta(days=offset_days)).isoformat()
            prio = rng.choice(cls.PRIORITIES)
            status = rng.choice(cls.STATUSES)
            cat = rng.choice(cls.CATEGORIES)
            title = rng.choice(cls.TITLES)

            tasks.append({
                "id": i,
                "title": f"{title} (Track #{i})",
                "description": f"Detailed architectural ticket specification for {title.lower()}.",
                "category": cat,
                "priority": prio,
                "status": status,
                "due_date": due,
                "estimated_hours": rng.choice([2, 4, 8, 16, 24]),
                "assigned_to_id": rng.choice([1, 2, 3, 4]),
                "team_id": rng.choice([1, 2]),
                "tags": f"{cat.lower()},{prio.lower()}"
            })

        return tasks
