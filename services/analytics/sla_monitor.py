"""
Service Level Agreement (SLA) Monitor, Deadline Tracker, and Escalation Engine.
Enforces resolution thresholds by priority, monitors aging tickets, and fires breach alarms.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum


class SLABreachLevel(str, Enum):
    OK = "OK"
    APPROACHING = "APPROACHING"  # > 75% elapsed
    BREACHED = "BREACHED"        # > 100% elapsed
    CRITICAL_BREACH = "CRITICAL_BREACH" # > 150% elapsed


@dataclass
class PrioritySLAConfig:
    """Configured target resolution thresholds in hours."""
    critical_hours: float = 4.0
    high_hours: float = 24.0
    medium_hours: float = 72.0
    low_hours: float = 168.0  # 1 week

    def get_hours_for_priority(self, priority: str) -> float:
        p = priority.capitalize()
        if p == "Critical":
            return self.critical_hours
        elif p == "High":
            return self.high_hours
        elif p == "Medium":
            return self.medium_hours
        else:
            return self.low_hours


@dataclass
class SLAPolicy:
    """Complete SLA Policy configuration for an organization or department."""
    policy_id: str
    name: str
    config: PrioritySLAConfig = field(default_factory=PrioritySLAConfig)
    business_hours_only: bool = False
    escalation_email: Optional[str] = None


@dataclass
class SLABreachEvent:
    """Audit record fired when a ticket violates its target threshold."""
    task_id: int
    task_title: str
    priority: str
    target_hours: float
    elapsed_hours: float
    breach_level: SLABreachLevel
    assigned_to_id: Optional[int]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SLAMonitor:
    """Evaluates task age and flags SLA compliance risks."""

    def __init__(self, policy: Optional[SLAPolicy] = None):
        self.policy = policy or SLAPolicy(policy_id="default", name="Standard Corporate SLA")

    def evaluate_task(self, task: Dict[str, Any], current_time: Optional[datetime] = None) -> Tuple[SLABreachLevel, float, float]:
        """
        Evaluate a task dictionary.
        Returns (breach_level, target_hours, elapsed_hours).
        """
        now = current_time or datetime.now(timezone.utc)
        status = task.get("status", "Pending")

        # Completed tasks no longer accumulate breach time
        if status in ("Completed", "Archived"):
            return SLABreachLevel.OK, 0.0, 0.0

        priority = task.get("priority", "Medium")
        target_hours = self.policy.config.get_hours_for_priority(priority)

        created_at_raw = task.get("created_at")
        if not created_at_raw:
            return SLABreachLevel.OK, target_hours, 0.0

        if isinstance(created_at_raw, str):
            try:
                # Handle ISO formatting
                created_at = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
            except ValueError:
                return SLABreachLevel.OK, target_hours, 0.0
        elif isinstance(created_at_raw, datetime):
            created_at = created_at_raw
        else:
            return SLABreachLevel.OK, target_hours, 0.0

        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        delta = now - created_at
        elapsed_hours = round(delta.total_seconds() / 3600.0, 2)

        ratio = elapsed_hours / max(0.1, target_hours)

        if ratio >= 1.5:
            level = SLABreachLevel.CRITICAL_BREACH
        elif ratio >= 1.0:
            level = SLABreachLevel.BREACHED
        elif ratio >= 0.75:
            level = SLABreachLevel.APPROACHING
        else:
            level = SLABreachLevel.OK

        return level, target_hours, elapsed_hours

    def scan_tasks(self, tasks: List[Dict[str, Any]]) -> List[SLABreachEvent]:
        """Scans a batch of active tickets and produces breach notifications."""
        events = []
        for t in tasks:
            lvl, target, elapsed = self.evaluate_task(t)
            if lvl in (SLABreachLevel.APPROACHING, SLABreachLevel.BREACHED, SLABreachLevel.CRITICAL_BREACH):
                events.append(SLABreachEvent(
                    task_id=t.get("id", 0),
                    task_title=t.get("title", "Untitled"),
                    priority=t.get("priority", "Medium"),
                    target_hours=target,
                    elapsed_hours=elapsed,
                    breach_level=lvl,
                    assigned_to_id=t.get("assigned_to_id")
                ))
        return events
