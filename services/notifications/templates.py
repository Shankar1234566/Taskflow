"""
Notification Formatting and Template Rendering Engine.
Builds styled HTML emails, Markdown snippets, and mobile push notification text.
"""
from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class MessagePayload:
    title: str
    body_text: str
    action_url: str
    action_label: str
    details: Dict[str, str] = field(default_factory=dict)


class NotificationTemplateEngine:
    """Formats event notifications into channel-tailored templates."""

    @staticmethod
    def render_task_assigned(task_title: str, task_id: int, assigner_name: str, due_date: str) -> MessagePayload:
        return MessagePayload(
            title=f"New Task Assigned: #{task_id} {task_title}",
            body_text=f"{assigner_name} assigned you to work on '{task_title}'. Target completion date: {due_date or 'None specified'}.",
            action_url=f"/#tasks/{task_id}",
            action_label="View Deliverable",
            details={"Task ID": str(task_id), "Due Date": due_date or "Flexible", "Assigned By": assigner_name}
        )

    @staticmethod
    def render_review_submitted(task_title: str, task_id: int, author_name: str, pr_link: str) -> MessagePayload:
        return MessagePayload(
            title=f"Deliverable Ready for Review: #{task_id} {task_title}",
            body_text=f"{author_name} submitted work for review with pull request: {pr_link or 'No link'}.",
            action_url=f"/#reviews/{task_id}",
            action_label="Review & Approve",
            details={"Task ID": str(task_id), "Author": author_name, "PR Link": pr_link or "N/A"}
        )

    @staticmethod
    def render_sla_alert(task_title: str, task_id: int, priority: str, elapsed_hours: float) -> MessagePayload:
        return MessagePayload(
            title=f"⚠️ SLA Deadline Alert: #{task_id} ({priority})",
            body_text=f"Ticket has been open for {elapsed_hours:.1f} hours and requires immediate engineering attention.",
            action_url=f"/#tasks/{task_id}",
            action_label="Intervene Now",
            details={"Task ID": str(task_id), "Priority": priority, "Age": f"{elapsed_hours:.1f}h"}
        )
