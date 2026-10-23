"""
GitHub Webhook Receiver and Automated Task Closer.
Parses git commits, PR descriptions for 'Fixes #123', and automatically moves tasks to 'In Review' or 'Completed'.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import re


@dataclass
class GitHubPullRequest:
    pr_number: int
    title: str
    author: str
    html_url: str
    state: str  # "open", "closed"
    merged: bool
    body: str


@dataclass
class GitHubWebhookPayload:
    action: str
    pull_request: Optional[GitHubPullRequest] = None
    repository_name: str = ""
    sender: str = ""


class GitHubIntegration:
    """Processes incoming GitHub webhooks and coordinates Taskflow status changes."""

    CLOSING_KEYWORDS_REGEX = re.compile(r"(?:close|closes|closed|fix|fixes|fixed|resolve|resolves|resolved)\s+#(\d+)", re.IGNORECASE)

    @classmethod
    def parse_task_references(cls, text: str) -> List[int]:
        """Extracts task IDs referenced in commit or PR bodies (e.g. 'Fixes #42')."""
        if not text:
            return []
        matches = cls.CLOSING_KEYWORDS_REGEX.findall(text)
        return [int(m) for m in matches]

    @classmethod
    def handle_pr_webhook(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process PR webhook payload.
        Returns directives for Taskflow (e.g. mark in review or mark completed).
        """
        action = payload.get("action", "")
        pr_data = payload.get("pull_request") or {}

        pr = GitHubPullRequest(
            pr_number=pr_data.get("number", 0),
            title=pr_data.get("title", ""),
            author=pr_data.get("user", {}).get("login", ""),
            html_url=pr_data.get("html_url", ""),
            state=pr_data.get("state", "open"),
            merged=pr_data.get("merged", False),
            body=pr_data.get("body") or ""
        )

        task_ids = cls.parse_task_references(pr.title + " " + pr.body)

        result = {
            "pr_number": pr.pr_number,
            "pr_url": pr.html_url,
            "referenced_task_ids": task_ids,
            "suggested_action": "NONE",
            "proof_of_work_link": pr.html_url
        }

        if action in ("opened", "reopened", "ready_for_review"):
            result["suggested_action"] = "MOVE_TO_REVIEW"
        elif action == "closed" and pr.merged:
            result["suggested_action"] = "MARK_COMPLETED"

        return result
