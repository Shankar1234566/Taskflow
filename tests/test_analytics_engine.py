"""
Unit Tests for Analytics, Velocity Calculations, and SLA Monitor.
"""
from datetime import date
from services.analytics import (
    SprintMetricsCalculator, SprintSnapshot, MonteCarloSimulator,
    WorkloadAnalyzer, SLAMonitor, SLABreachLevel, PrioritySLAConfig,
    MetricAggregator
)


def test_velocity_forecasting():
    history = [
        SprintSnapshot("S1", "Sprint 1", "2026-09-01", "2026-09-14", 30.0, 28.0, 10, 9),
        SprintSnapshot("S2", "Sprint 2", "2026-09-15", "2026-09-28", 32.0, 32.0, 12, 12),
        SprintSnapshot("S3", "Sprint 3", "2026-09-29", "2026-10-12", 35.0, 34.0, 11, 10)
    ]
    forecast = SprintMetricsCalculator.compute_velocity_forecast(history)
    assert forecast.average_velocity > 30.0
    assert forecast.median_velocity == 32.0


def test_monte_carlo_simulation():
    sim = MonteCarloSimulator([25.0, 30.0, 35.0], random_seed=42)
    res = sim.simulate_sprints_needed(total_backlog_points=90.0, iterations=500)
    assert res["p50_sprints"] in (3, 4)
    assert res["p95_sprints"] >= res["p50_sprints"]


def test_workload_analyzer():
    users = [{"id": 1, "username": "Alice", "role": "Member", "team_id": 1}]
    tasks = [
        {"id": 1, "assigned_to_id": 1, "status": "In Progress", "estimated_hours": 30.0},
        {"id": 2, "assigned_to_id": 1, "status": "In Progress", "estimated_hours": 20.0}
    ]
    balance = WorkloadAnalyzer.analyze_team(1, users, tasks, weekly_capacity_hours=40.0)
    assert balance.overloaded_members_count == 1
    assert balance.member_capacities[0].is_overloaded is True


def test_sla_monitor():
    monitor = SLAMonitor()
    task = {
        "id": 1,
        "title": "Production Outage",
        "priority": "Critical",
        "created_at": "2026-10-20T10:00:00Z",
        "status": "In Progress"
    }
    lvl, target, elapsed = monitor.evaluate_task(task)
    assert lvl == SLABreachLevel.CRITICAL_BREACH
    assert target == 4.0
