"""
Outgoing Webhook Dispatcher with HMAC-SHA256 Cryptographic Signatures.
Allows external services to subscribe to Taskflow events securely.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import hashlib
import hmac
import json
import logging

logger = logging.getLogger("taskflow.services.webhooks")


@dataclass
class OutgoingWebhookConfig:
    webhook_id: str
    target_url: str
    secret_token: str
    subscribed_events: List[str]
    is_active: bool = True


class WebhookManager:
    """Signs and formats outgoing HTTP POST webhooks."""

    def __init__(self):
        self._endpoints: List[OutgoingWebhookConfig] = []

    def register(self, endpoint: OutgoingWebhookConfig) -> None:
        self._endpoints.append(endpoint)

    @staticmethod
    def generate_signature(secret: str, payload_bytes: bytes) -> str:
        """Computes HMAC-SHA256 hex digest for payload authentication."""
        h = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256)
        return "sha256=" + h.hexdigest()

    def prepare_dispatch(self, event_type: str, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Prepares signed HTTP POST payloads for all matching active webhooks."""
        dispatches = []
        payload_body = json.dumps({
            "event": event_type,
            "data": payload,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, sort_keys=True)

        for ep in self._endpoints:
            if not ep.is_active:
                continue
            if "*" in ep.subscribed_events or event_type in ep.subscribed_events:
                sig = self.generate_signature(ep.secret_token, payload_body.encode("utf-8"))
                dispatches.append({
                    "url": ep.target_url,
                    "headers": {
                        "Content-Type": "application/json",
                        "X-Taskflow-Event": event_type,
                        "X-Taskflow-Signature": sig
                    },
                    "body": payload_body
                })

        return dispatches
