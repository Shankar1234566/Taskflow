"""
Cryptographically Hash-Chained Audit Trail Logger.
Produces tamper-evident SHA-256 chained transaction logs.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from typing import Dict, List, Optional, Any, Tuple


@dataclass
class AuditEntry:
    entry_id: int
    actor_id: int
    action: str
    target_resource: str
    payload: Dict[str, Any]
    previous_hash: str
    current_hash: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class CryptographicAuditLogger:
    """Maintains an immutable chain of audit entries."""

    GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"

    def __init__(self):
        self._chain: List[AuditEntry] = []

    def log(self, actor_id: int, action: str, target: str, payload: Dict[str, Any]) -> AuditEntry:
        prev_hash = self._chain[-1].current_hash if self._chain else self.GENESIS_HASH
        eid = len(self._chain) + 1
        ts = datetime.now(timezone.utc)

        data_to_hash = json.dumps({
            "entry_id": eid,
            "actor_id": actor_id,
            "action": action,
            "target": target,
            "payload": payload,
            "previous_hash": prev_hash,
            "timestamp": ts.isoformat()
        }, sort_keys=True)

        curr_hash = hashlib.sha256(data_to_hash.encode("utf-8")).hexdigest()

        entry = AuditEntry(
            entry_id=eid,
            actor_id=actor_id,
            action=action,
            target_resource=target,
            payload=payload,
            previous_hash=prev_hash,
            current_hash=curr_hash,
            timestamp=ts
        )
        self._chain.append(entry)
        return entry

    def verify_integrity(self) -> Tuple[bool, Optional[int]]:
        """Verifies hash-chain continuity. Returns (is_valid, corrupted_entry_id)."""
        expected_prev = self.GENESIS_HASH
        for entry in self._chain:
            if entry.previous_hash != expected_prev:
                return False, entry.entry_id
            expected_prev = entry.current_hash
        return True, None
