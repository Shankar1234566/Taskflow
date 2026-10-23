"""
Slack Bot Integration and Interactive Block Kit UI Builder.
Formats Slack slash commands, interactive buttons (Approve/Reject), and daily channel alerts.
"""
from dataclasses import dataclass
from typing import Dict, List, Any


class SlackMessageBuilder:
    """Constructs Slack Block Kit JSON payloads."""

    @staticmethod
    def build_task_card(task: Dict[str, Any], base_url: str = "http://localhost:5000") -> Dict[str, Any]:
        tid = task.get("id")
        title = task.get("title", "Untitled")
        priority = task.get("priority", "Medium")
        status = task.get("status", "Pending")

        return {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Task #{tid}: {title}*\\nStatus: `{status}` | Priority: *{priority}*"
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Open in Taskflow"},
                            "url": f"{base_url}/#tasks/{tid}",
                            "action_id": "view_task"
                        }
                    ]
                }
            ]
        }


class SlackBotIntegration:
    """Interprets incoming Slack slash commands (e.g. `/taskflow create`)."""

    @staticmethod
    def handle_slash_command(command: str, text: str, user_name: str) -> Dict[str, Any]:
        parts = text.strip().split()
        subcmd = parts[0] if parts else "help"

        if subcmd == "create":
            title = " ".join(parts[1:]) or "New Task"
            return {
                "response_type": "ephemeral",
                "text": f"✅ Creating task: *{title}* (Author: @{user_name})"
            }
        else:
            return {
                "response_type": "ephemeral",
                "text": "Taskflow Slack Bot commands:\\n- `/taskflow create [title]`\\n- `/taskflow list`\\n- `/taskflow status`"
            }
