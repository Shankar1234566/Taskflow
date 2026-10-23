"""
Enterprise Notification Subsystem.
Dispatches alerts, renders formatted templates, manages in-memory event bus, and aggregates digests.
"""
from .dispatcher import NotificationDispatcher, NotificationChannel, NotificationMessage, DeliveryStatus
from .templates import NotificationTemplateEngine, MessagePayload
from .event_bus import EventBus, EventSubscription, SystemEvent
from .digest import DigestAggregator, UserDigestPreference

__all__ = [
    "NotificationDispatcher", "NotificationChannel", "NotificationMessage", "DeliveryStatus",
    "NotificationTemplateEngine", "MessagePayload",
    "EventBus", "EventSubscription", "SystemEvent",
    "DigestAggregator", "UserDigestPreference"
]
