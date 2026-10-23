"""
JSON Export and Complete Workspace Archival Engine.
Serializes full relational task hierarchies with metadata, checksums, and version tags.
"""
from datetime import datetime, timezone
import hashlib
import json
from typing import Dict, List, Any


class JSONExporter:
    """Encapsulates system state into standard JSON export packets."""

    @classmethod
    def export_dataset(cls, tasks: List[Dict[str, Any]], teams: List[Dict[str, Any]], users: List[Dict[str, Any]]) -> str:
        data = {
            "version": "2.5.0",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "teams": teams,
            "users": users,
            "tasks": tasks
        }
        encoded = json.dumps(data, indent=2, sort_keys=True)
        chk = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        data["checksum"] = chk
        return json.dumps(data, indent=2, sort_keys=True)
