"""
Sprint Metrics, Velocity Forecaster, and Monte Carlo Simulation Engine.
Computes delivery velocity trends, burndown curves, and probabilistic milestone completion dates.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Any
import math
import random


@dataclass
class SprintSnapshot:
    """Historical record of sprint outcomes."""
    sprint_id: str
    sprint_name: str
    start_date: str
    end_date: str
    planned_story_points: float
    completed_story_points: float
    total_tasks_planned: int
    total_tasks_completed: int
    unplanned_tasks_added: int = 0
    spillover_tasks: int = 0

    @property
    def commitment_reliability_ratio(self) -> float:
        """Percentage of committed scope actually completed."""
        if self.planned_story_points <= 0:
            return 0.0
        return round(min(1.0, self.completed_story_points / self.planned_story_points) * 100, 2)

    @property
    def task_completion_rate(self) -> float:
        """Percentage of tasks completed."""
        total = self.total_tasks_planned + self.unplanned_tasks_added
        if total <= 0:
            return 0.0
        return round((self.total_tasks_completed / total) * 100, 2)


@dataclass
class BurndownPoint:
    """A single day point on an ideal vs actual burndown trajectory."""
    day_index: int
    calendar_date: str
    ideal_remaining: float
    actual_remaining: float
    scope_change: float = 0.0


@dataclass
class VelocityForecast:
    """Forecasting projections based on historical sprint performance."""
    average_velocity: float
    median_velocity: float
    standard_deviation: float
    confidence_80_percentile: float
    confidence_95_percentile: float
    trend_slope: float  # Positive = accelerating, Negative = decelerating


class SprintMetricsCalculator:
    """Core calculation engine for sprint delivery performance."""

    @staticmethod
    def calculate_burndown_series(
        start_date: date,
        sprint_days: int,
        initial_points: float,
        daily_completed_points: List[float]
    ) -> List[BurndownPoint]:
        """Generates daily ideal vs actual burndown data points."""
        series: List[BurndownPoint] = []
        ideal_decrement = initial_points / max(1, sprint_days)
        current_actual = initial_points

        for day in range(sprint_days + 1):
            cal_date = (start_date + timedelta(days=day)).isoformat()
            ideal = max(0.0, initial_points - (day * ideal_decrement))

            if day == 0:
                series.append(BurndownPoint(day, cal_date, round(ideal, 2), round(current_actual, 2)))
            else:
                completed = daily_completed_points[day - 1] if day - 1 < len(daily_completed_points) else 0.0
                current_actual = max(0.0, current_actual - completed)
                series.append(BurndownPoint(day, cal_date, round(ideal, 2), round(current_actual, 2)))

        return series

    @staticmethod
    def compute_velocity_forecast(history: List[SprintSnapshot]) -> VelocityForecast:
        """Computes statistical velocity metrics and trends over sprint history."""
        if not history:
            return VelocityForecast(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

        velocities = [s.completed_story_points for s in history]
        n = len(velocities)
        avg = sum(velocities) / n

        # Median
        sorted_v = sorted(velocities)
        if n % 2 == 1:
            median = sorted_v[n // 2]
        else:
            median = (sorted_v[n // 2 - 1] + sorted_v[n // 2]) / 2.0

        # Standard Deviation
        variance = sum((x - avg) ** 2 for x in velocities) / max(1, n - 1)
        std_dev = math.sqrt(variance)

        # Confidence intervals assuming normal distribution
        # 80% CI: Z = 1.282; 95% CI: Z = 1.645 (one-tailed lower bounds)
        conf_80 = max(0.0, avg - (1.282 * (std_dev / math.sqrt(n))))
        conf_95 = max(0.0, avg - (1.645 * (std_dev / math.sqrt(n))))

        # Simple linear trend slope (least squares regression)
        x_vals = list(range(n))
        x_bar = sum(x_vals) / n
        numerator = sum((x_vals[i] - x_bar) * (velocities[i] - avg) for i in range(n))
        denominator = sum((x - x_bar) ** 2 for x in x_vals)
        slope = numerator / denominator if denominator != 0 else 0.0

        return VelocityForecast(
            average_velocity=round(avg, 2),
            median_velocity=round(median, 2),
            standard_deviation=round(std_dev, 2),
            confidence_80_percentile=round(conf_80, 2),
            confidence_95_percentile=round(conf_95, 2),
            trend_slope=round(slope, 3)
        )


class MonteCarloSimulator:
    """Probabilistic milestone completion simulator running Monte Carlo iterations."""

    def __init__(self, historical_velocities: List[float], random_seed: int = 42):
        self.velocities = historical_velocities if historical_velocities else [10.0]
        self.random = random.Random(random_seed)

    def simulate_sprints_needed(self, total_backlog_points: float, iterations: int = 5000) -> Dict[str, Any]:
        """Simulates number of sprints required to complete a given backlog size."""
        if total_backlog_points <= 0:
            return {"p50_sprints": 0, "p80_sprints": 0, "p95_sprints": 0, "distribution": {}}

        results = []
        for _ in range(iterations):
            remaining = total_backlog_points
            sprints = 0
            while remaining > 0 and sprints < 100:
                sampled_v = self.random.choice(self.velocities)
                remaining -= max(1.0, sampled_v)
                sprints += 1
            results.append(sprints)

        results.sort()
        p50 = results[int(iterations * 0.50)]
        p80 = results[int(iterations * 0.80)]
        p95 = results[int(iterations * 0.95)]

        # Frequency distribution
        dist = {}
        for r in results:
            dist[r] = dist.get(r, 0) + 1

        return {
            "total_backlog_points": total_backlog_points,
            "iterations": iterations,
            "p50_sprints": p50,
            "p80_sprints": p80,
            "p95_sprints": p95,
            "min_sprints": results[0],
            "max_sprints": results[-1],
            "distribution": dist
        }
