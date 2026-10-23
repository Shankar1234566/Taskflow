"""
In-Memory Event Bus with Publish/Subscribe Architecture.
Decouples database models and route handlers from downstream side-effects.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Callable, Any, Optional
import logging

logger = logging.getLogger("taskflow.services.event_bus")


@dataclass
class SystemEvent:
    """Encapsulates a broadcast domain event."""
    event_type: str  # "task.created", "task.status_changed", "task.assigned", etc.
    payload: Dict[str, Any]
    actor_id: Optional[int] = None
    event_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class EventSubscription:
    subscription_id: str
    event_pattern: str  # exact match or wildcard prefix like "task.*"
    callback: Callable[[SystemEvent], None]


class EventBus:
    """Central event broker for Taskflow services."""

    def __init__(self):
        self._subscribers: List[EventSubscription] = []
        self._event_history: List[SystemEvent] = []

    def subscribe(self, pattern: str, callback: Callable[[SystemEvent], None], sub_id: str = "") -> EventSubscription:
        sub = EventSubscription(
            subscription_id=sub_id or f"sub_{len(self._subscribers) + 1}",
            event_pattern=pattern,
            callback=callback
        )
        self._subscribers.append(sub)
        return sub

    def publish(self, event_type: str, payload: Dict[str, Any], actor_id: Optional[int] = None) -> SystemEvent:
        event = SystemEvent(
            event_type=event_type,
            payload=payload,
            actor_id=actor_id,
            event_id=f"evt_{len(self._event_history) + 1}"
        )
        self._event_history.append(event)

        for sub in self._subscribers:
            if self._matches_pattern(sub.event_pattern, event_type):
                try:
                    sub.callback(event)
                except Exception as e:
                    logger.error(f"Subscriber {sub.subscription_id} error handling {event_type}: {e}", exc_info=True)

        return event

    @staticmethod
    def _matches_pattern(pattern: str, event_type: str) -> bool:
        if pattern == "*" or pattern == event_type:
            return True
        if pattern.endswith(".*"):
            prefix = pattern[:-2]
            return event_type.startswith(prefix + ".")
        return False
