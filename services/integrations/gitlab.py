"""
GitLab Webhook Handler for Merge Requests and CI/CD Pipelines.
Syncs GitLab merge status and attaches pipeline build verification links.
"""
from dataclasses import dataclass
from typing import Dict, List, Any
import re


@dataclass
class GitLabMergeRequest:
    iid: int
    title: str
    url: str
    state: str  # "opened", "closed", "merged"
    description: str


class GitLabIntegration:
    """Interprets GitLab events and connects them to Taskflow deliverables."""

    REF_REGEX = re.compile(r"(?:resolves|closes|fixes)\s+#?(\d+)", re.IGNORECASE)

    @classmethod
    def process_merge_request_event(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        attrs = payload.get("object_attributes") or {}
        desc = attrs.get("description", "")
        title = attrs.get("title", "")

        task_ids = [int(x) for x in cls.REF_REGEX.findall(title + " " + desc)]

        state = attrs.get("state", "opened")
        action = attrs.get("action", "")

        suggested = "NONE"
        if state == "merged":
            suggested = "MARK_COMPLETED"
        elif action in ("open", "reopen", "update"):
            suggested = "MOVE_TO_REVIEW"

        return {
            "source": "gitlab",
            "mr_iid": attrs.get("iid"),
            "mr_url": attrs.get("url"),
            "referenced_task_ids": task_ids,
            "suggested_action": suggested
        }
