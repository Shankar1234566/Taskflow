"""
Bidirectional Jira Cloud & Server Synchronization Engine.
Maps Jira issues, story points, epics, and sprints to Taskflow tasks and teams.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Any


@dataclass
class JiraIssueMapping:
    jira_key: str  # e.g. "ENG-1042"
    taskflow_task_id: int
    jira_status: str
    taskflow_status: str
    last_synced_at: str


class JiraSyncEngine:
    """Translates between Atlassian Jira and Taskflow schemas."""

    STATUS_MAP = {
        "To Do": "Pending",
        "Open": "Pending",
        "In Progress": "In Progress",
        "In Review": "In Review",
        "Code Review": "In Review",
        "Done": "Completed",
        "Resolved": "Completed",
        "Closed": "Completed"
    }

    PRIORITY_MAP = {
        "Highest": "Critical",
        "High": "High",
        "Medium": "Medium",
        "Low": "Low",
        "Lowest": "Low"
    }

    @classmethod
    def map_jira_to_taskflow(cls, jira_payload: Dict[str, Any]) -> Dict[str, Any]:
        fields = jira_payload.get("fields", {})
        status_name = fields.get("status", {}).get("name", "To Do")
        prio_name = fields.get("priority", {}).get("name", "Medium")

        return {
            "title": fields.get("summary", "Untitled Jira Ticket"),
            "description": fields.get("description") or "",
            "status": cls.STATUS_MAP.get(status_name, "Pending"),
            "priority": cls.PRIORITY_MAP.get(prio_name, "Medium"),
            "category": fields.get("project", {}).get("name", "Jira Import"),
            "tags": f"jira,{jira_payload.get('key', '')}"
        }
