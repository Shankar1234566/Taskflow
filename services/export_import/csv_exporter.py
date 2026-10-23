"""
RFC 4180 Compliant CSV Export Streamer.
Exports tasks, team allocations, time estimates, and audit trails.
"""
import csv
import io
from typing import Dict, List, Any


class CSVExporter:
    """Exports task collections into CSV text streams."""

    COLUMNS = [
        "id", "title", "description", "category", "priority",
        "status", "due_date", "created_by", "assigned_to", "tags"
    ]

    @classmethod
    def export_tasks_to_csv(cls, tasks: List[Dict[str, Any]]) -> str:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=cls.COLUMNS, extrasaction="ignore")
        writer.writeheader()

        for t in tasks:
            row = {
                "id": t.get("id"),
                "title": t.get("title", ""),
                "description": (t.get("description") or "").replace("\n", " "),
                "category": t.get("category", ""),
                "priority": t.get("priority", "Medium"),
                "status": t.get("status", "Pending"),
                "due_date": t.get("due_date", ""),
                "created_by": t.get("created_by_name", ""),
                "assigned_to": t.get("assigned_to_name", ""),
                "tags": t.get("tags", "")
            }
            writer.writerow(row)

        return output.getvalue()
