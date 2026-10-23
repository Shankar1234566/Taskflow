"""
Daily and Weekly Digest Notification Aggregator.
Consolidates multiple activity alerts into a unified briefing email to reduce inbox fatigue.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Any


@dataclass
class UserDigestPreference:
    user_id: int
    receive_daily_digest: bool = True
    receive_weekly_report: bool = True
    quiet_hours_start: int = 22  # 10 PM
    quiet_hours_end: int = 7     # 7 AM


@dataclass
class DigestSummary:
    user_id: int
    assigned_count: int = 0
    completed_count: int = 0
    review_requested_count: int = 0
    overdue_count: int = 0
    events: List[Dict[str, Any]] = field(default_factory=list)

    def is_empty(self) -> bool:
        return self.assigned_count == 0 and self.completed_count == 0 and self.overdue_count == 0


class DigestAggregator:
    """Builds summarized notification digests for users."""

    def __init__(self):
        self._user_queues: Dict[int, List[Dict[str, Any]]] = {}

    def queue_event(self, user_id: int, event_type: str, details: Dict[str, Any]) -> None:
        if user_id not in self._user_queues:
            self._user_queues[user_id] = []
        self._user_queues[user_id].append({
            "type": event_type,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    def generate_digest(self, user_id: int) -> DigestSummary:
        events = self._user_queues.pop(user_id, [])
        summary = DigestSummary(user_id=user_id, events=events)

        for e in events:
            t = e.get("type")
            if t == "task.assigned":
                summary.assigned_count += 1
            elif t == "task.completed":
                summary.completed_count += 1
            elif t == "review.requested":
                summary.review_requested_count += 1
            elif t == "task.overdue":
                summary.overdue_count += 1

        return summary
