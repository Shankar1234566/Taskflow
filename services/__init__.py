"""
Taskflow Enterprise Services Layer.
Provides workflow orchestration, analytics, notification dispatching,
integrations, export/import pipelines, compliance auditing, and RBAC policy evaluation.
"""
__version__ = "2.5.0"

# Services package for TaskFlow
from .notification_service import (
    dispatch_event,
    notify_status_transition,
    notify_auto_routed_bug,
    notify_unblocked_dependents,
    notify_task_assigned,
    notify_review_requested,
    notify_feedback_submitted,
    add_watcher,
    remove_watcher,
    get_task_watchers
)
