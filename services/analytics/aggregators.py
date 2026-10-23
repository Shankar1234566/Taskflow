"""
Time-Series Metrics Rollup, Category Distributions, and Performance Aggregators.
Synthesizes historical trends, moving averages, and departmental completion ratios.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Any


@dataclass
class TimeSeriesRollup:
    """Aggregated ticket statistics for a specific date window."""
    window_start: str
    window_end: str
    created_count: int
    completed_count: int
    net_throughput: int  # completed - created
    average_cycle_time_hours: float


@dataclass
class CategoryDistribution:
    """Distribution breakdown for a single project category or label."""
    category_name: str
    total_tasks: int
    completed_tasks: int
    in_progress_tasks: int
    overdue_tasks: int
    completion_rate: float


class MetricAggregator:
    """Aggregates raw task records into executive reporting summaries."""

    @staticmethod
    def aggregate_by_category(tasks: List[Dict[str, Any]]) -> List[CategoryDistribution]:
        """Groups tasks by category and computes completion rates."""
        buckets: Dict[str, Dict[str, int]] = {}

        for t in tasks:
            cat = t.get("category") or "General"
            if cat not in buckets:
                buckets[cat] = {"total": 0, "completed": 0, "in_progress": 0, "overdue": 0}

            b = buckets[cat]
            b["total"] += 1
            status = t.get("status", "Pending")

            if status in ("Completed", "Done") or t.get("completed"):
                b["completed"] += 1
            elif status == "In Progress":
                b["in_progress"] += 1

            if t.get("is_overdue"):
                b["overdue"] += 1

        results = []
        for cat, data in sorted(buckets.items()):
            tot = data["total"]
            done = data["completed"]
            rate = round((done / tot) * 100, 2) if tot > 0 else 0.0

            results.append(CategoryDistribution(
                category_name=cat,
                total_tasks=tot,
                completed_tasks=done,
                in_progress_tasks=data["in_progress"],
                overdue_tasks=data["overdue"],
                completion_rate=rate
            ))

        return results

    @staticmethod
    def generate_7day_rolling_summary(tasks: List[Dict[str, Any]], end_date: Optional[date] = None) -> List[TimeSeriesRollup]:
        """Produces a 7-day rolling window throughput summary."""
        target_end = end_date or date.today()
        rollups = []

        for offset in range(6, -1, -1):
            day = target_end - timedelta(days=offset)
            day_str = day.isoformat()

            created = 0
            completed = 0
            for t in tasks:
                c_date = str(t.get("created_at") or "")[:10]
                comp_date = str(t.get("completed_at") or "")[:10]
                if c_date == day_str:
                    created += 1
                if comp_date == day_str:
                    completed += 1

            rollups.append(TimeSeriesRollup(
                window_start=day_str,
                window_end=day_str,
                created_count=created,
                completed_count=completed,
                net_throughput=completed - created,
                average_cycle_time_hours=0.0
            ))

        return rollups
