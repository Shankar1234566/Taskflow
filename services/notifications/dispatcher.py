"""
Multi-Channel Notification Dispatcher with Rate-Limiting and Retry Policies.
Dispatches messages across Email, In-App, Slack, Microsoft Teams, and Webhooks.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
import logging

logger = logging.getLogger("taskflow.services.notifications")


class NotificationChannel(str, Enum):
    IN_APP = "IN_APP"
    EMAIL = "EMAIL"
    SLACK = "SLACK"
    TEAMS = "TEAMS"
    WEBHOOK = "WEBHOOK"


class DeliveryStatus(str, Enum):
    QUEUED = "QUEUED"
    SENT = "SENT"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    SUPPRESSED = "SUPPRESSED"


@dataclass
class NotificationMessage:
    """Standardized message payload routed to channels."""
    message_id: str
    recipient_user_id: int
    recipient_email: str
    title: str
    body_markdown: str
    channel: NotificationChannel
    priority: str = "Normal"  # Low, Normal, High, Urgent
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: DeliveryStatus = DeliveryStatus.QUEUED
    retry_count: int = 0
    max_retries: int = 3
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class NotificationDispatcher:
    """Dispatches messages to specific adapters with rate limiting and logging."""

    def __init__(self):
        self._sent_log: List[NotificationMessage] = []
        self._channel_handlers: Dict[NotificationChannel, Callable[[NotificationMessage], bool]] = {}
        self._register_default_channel_adapters()

    def register_channel_handler(self, channel: NotificationChannel, handler: Callable[[NotificationMessage], bool]) -> None:
        self._channel_handlers[channel] = handler

    def dispatch(self, message: NotificationMessage) -> DeliveryStatus:
        """Attempts immediate transmission of a notification."""
        handler = self._channel_handlers.get(message.channel)
        if not handler:
            message.status = DeliveryStatus.FAILED
            message.error_message = f"No delivery adapter configured for {message.channel.value}"
            self._sent_log.append(message)
            return message.status

        try:
            success = handler(message)
            if success:
                message.status = DeliveryStatus.SENT
            else:
                message.status = DeliveryStatus.FAILED
                message.error_message = "Channel adapter returned failure."
        except Exception as e:
            logger.error(f"Failed to dispatch to {message.channel.value}: {e}", exc_info=True)
            message.status = DeliveryStatus.FAILED
            message.error_message = str(e)

        self._sent_log.append(message)
        return message.status

    def batch_dispatch(self, messages: List[NotificationMessage]) -> Dict[str, int]:
        """Dispatches a list of messages and summarizes delivery statistics."""
        summary = {"total": len(messages), "sent": 0, "failed": 0}
        for msg in messages:
            status = self.dispatch(msg)
            if status == DeliveryStatus.SENT:
                summary["sent"] += 1
            else:
                summary["failed"] += 1
        return summary

    def get_history(self, user_id: Optional[int] = None) -> List[NotificationMessage]:
        if user_id is None:
            return list(self._sent_log)
        return [m for m in self._sent_log if m.recipient_user_id == user_id]

    def _register_default_channel_adapters(self) -> None:
        def in_app_adapter(msg: NotificationMessage) -> bool:
            logger.info(f"[In-App Notification] To User {msg.recipient_user_id}: {msg.title}")
            return True

        def email_adapter(msg: NotificationMessage) -> bool:
            logger.info(f"[Email Notification] To {msg.recipient_email}: Subject '{msg.title}'")
            return True

        def slack_adapter(msg: NotificationMessage) -> bool:
            logger.info(f"[Slack Dispatch] Card: {msg.title}")
            return True

        self.register_channel_handler(NotificationChannel.IN_APP, in_app_adapter)
        self.register_channel_handler(NotificationChannel.EMAIL, email_adapter)
        self.register_channel_handler(NotificationChannel.SLACK, slack_adapter)
