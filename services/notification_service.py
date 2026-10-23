import logging
from datetime import datetime, timezone
from models import db, Notification, TaskWatcher, Task, User, Team

logger = logging.getLogger(__name__)

# Standard Jira-mirrored event types
EVENT_TASK_ASSIGNED = "TASK_ASSIGNED"
EVENT_STATUS_CHANGED = "STATUS_CHANGED"
EVENT_BUG_ROUTED = "BUG_ROUTED"
EVENT_BLOCKER_RESOLVED = "BLOCKER_RESOLVED"
EVENT_REVIEW_REQUESTED = "REVIEW_REQUESTED"
EVENT_FEEDBACK_SUBMITTED = "FEEDBACK_SUBMITTED"
EVENT_HIGH_PRIORITY_BUG = "HIGH_PRIORITY_BUG"

def get_task_watchers(task_id):
    """Returns list of user IDs watching the specified task."""
    try:
        watchers = TaskWatcher.query.filter_by(task_id=task_id).all()
        return [w.user_id for w in watchers]
    except Exception as e:
        logger.error(f"Error fetching watchers for task {task_id}: {e}")
        return []

def add_watcher(task_id, user_id):
    """Subscribes a user as a watcher to a task if not already watching."""
    if not task_id or not user_id:
        return False
    try:
        existing = TaskWatcher.query.filter_by(task_id=task_id, user_id=user_id).first()
        if not existing:
            sub = TaskWatcher(task_id=task_id, user_id=user_id, subscribed_at=datetime.utcnow())
            db.session.add(sub)
            db.session.commit()
            return True
        return False
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error adding watcher for task {task_id}, user {user_id}: {e}")
        return False

def remove_watcher(task_id, user_id):
    """Unsubscribes a user from watching a task."""
    if not task_id or not user_id:
        return False
    try:
        existing = TaskWatcher.query.filter_by(task_id=task_id, user_id=user_id).first()
        if existing:
            db.session.delete(existing)
            db.session.commit()
            return True
        return False
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error removing watcher for task {task_id}, user {user_id}: {e}")
        return False

def dispatch_event(event_type, task, actor_id=None, metadata=None, recipient_ids=None, priority="Normal", custom_title=None, custom_message=None):
    """
    Decoupled Event Bus & Dispatcher Service.
    Aggregates target recipients based on Jira-style subscription rules:
    - Primary assignee
    - Deliverable creator
    - Team Lead (for review/bugs/high-priority items)
    - All subscribed watchers from TaskWatcher
    - Specific explicit recipients if passed
    Dedupes recipients and filters out actor_id (the user who initiated the event).
    Creates and commits Notification records in bulk.
    """
    if not task and not recipient_ids:
        return []

    metadata = metadata or {}
    task_id = task.id if task else metadata.get("task_id")
    target_recipients = set()

    # Explicit recipients if provided
    if recipient_ids:
        target_recipients.update(recipient_ids)

    # Jira-style recipient resolution based on event type and task relationships
    if task:
        assignee_id = task.assigned_to_id or task.user_id
        creator_id = task.created_by_id

        # 1. Always include registered watchers
        watchers = get_task_watchers(task.id)
        target_recipients.update(watchers)

        # 2. Include creator
        if creator_id:
            target_recipients.add(creator_id)

        # 3. Include assignee
        if assignee_id:
            target_recipients.add(assignee_id)

        # 4. Resolve team lead
        team_lead_id = None
        if task.team_id:
            team = db.session.get(Team, task.team_id)
            if team and team.lead_id:
                team_lead_id = team.lead_id

        if event_type in (EVENT_REVIEW_REQUESTED, EVENT_BUG_ROUTED, EVENT_HIGH_PRIORITY_BUG) and team_lead_id:
            target_recipients.add(team_lead_id)

    # Dedup and exclude the actor who triggered the action
    if actor_id:
        target_recipients.discard(actor_id)

    if not target_recipients:
        return []

    # Retrieve actor name for friendly notifications
    actor_name = "A team member"
    if actor_id:
        actor = db.session.get(User, actor_id)
        if actor:
            actor_name = actor.username or actor.name

    task_title = task.title if task else metadata.get("task_title", "Deliverable")
    target_url = metadata.get("target_url") or (f"#task-{task_id}" if task_id else "")

    # Build title and message templates if not customized
    title = custom_title
    message = custom_message

    if not title or not message:
        if event_type == EVENT_STATUS_CHANGED:
            old_status = metadata.get("old_status", "Pending")
            new_status = metadata.get("new_status", task.status if task else "Updated")
            title = title or f"Status: {task_title}"
            message = message or f'{actor_name} moved deliverable "{task_title}" from {old_status} to {new_status}.'

        elif event_type == EVENT_TASK_ASSIGNED:
            title = title or f"Assignment: {task_title}"
            message = message or f'You have been assigned to deliverable "{task_title}" by {actor_name}.'

        elif event_type == EVENT_BUG_ROUTED:
            title = title or f"Bug Routed: {task_title}"
            message = message or f'Bug #{task_id} "{task_title}" was auto-routed to your queue for immediate triage.'

        elif event_type == EVENT_HIGH_PRIORITY_BUG:
            title = title or f"🚨 Urgent Bug Alert: {task_title}"
            message = message or f'Critical/High Priority bug logged: "{task_title}". Immediate investigation required.'
            priority = "Urgent"

        elif event_type == EVENT_BLOCKER_RESOLVED:
            blocker_title = metadata.get("blocker_title", "Prerequisite deliverable")
            title = title or f"🔓 Deliverable Unblocked: {task_title}"
            message = message or f'Your deliverable "{task_title}" is now unblocked! Prerequisite "{blocker_title}" has completed.'

        elif event_type == EVENT_REVIEW_REQUESTED:
            title = title or f"Review Requested: {task_title}"
            message = message or f'{actor_name} submitted proof of work for "{task_title}" and requested your review.'

        elif event_type == EVENT_FEEDBACK_SUBMITTED:
            review_action = metadata.get("review_action", "reviewed")
            feedback = metadata.get("feedback", "")
            if review_action == "approve":
                title = title or f"✅ Approved: {task_title}"
                message = message or f'{actor_name} approved your deliverable "{task_title}". Marked as Completed.'
            else:
                title = title or f"⚠️ Changes Requested: {task_title}"
                message = message or f'{actor_name} requested revisions on "{task_title}": {feedback or "Check review comments."}'
        else:
            title = title or f"Update on {task_title}"
            message = message or f'{actor_name} updated "{task_title}".'

    # Build notification objects
    now = datetime.utcnow()
    notifications = []
    for r_id in target_recipients:
        notif = Notification(
            recipient_id=r_id,
            sender_id=actor_id,
            task_id=task_id,
            event_type=event_type,
            title=title[:120],
            message=message,
            target_url=target_url,
            is_read=False,
            priority=priority,
            created_at=now
        )
        notifications.append(notif)
        db.session.add(notif)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to commit bulk notifications: {e}")
        return []

    return notifications


# Specialized Dispatcher Helpers

def notify_status_transition(task, old_status, new_status, actor_id):
    """Notifies creator, assignee, and watchers when a task status changes."""
    if not task or old_status == new_status:
        return []

    notifs = dispatch_event(
        event_type=EVENT_STATUS_CHANGED,
        task=task,
        actor_id=actor_id,
        metadata={"old_status": old_status, "new_status": new_status}
    )

    # When deliverable completes, alert all dependents waiting on it
    if new_status == "Completed":
        notify_unblocked_dependents(task)

    return notifs


def notify_auto_routed_bug(task, assigned_engineer, actor_id=None):
    """
    Dispatches automated bug routing notification to the designated engineer and lead.
    Triggers urgent alerts if bug priority is Critical or High.
    """
    if not task or not assigned_engineer:
        return []

    is_urgent = (task.priority or "").capitalize() in ("Critical", "High")
    priority_level = "Urgent" if is_urgent else "Normal"

    # Auto-subscribe assigned engineer to task updates
    add_watcher(task.id, assigned_engineer.id)

    # If creator exists, also subscribe creator
    if task.created_by_id:
        add_watcher(task.id, task.created_by_id)

    recipients = {assigned_engineer.id}
    if task.team_id:
        team = db.session.get(Team, task.team_id)
        if team and team.lead_id:
            recipients.add(team.lead_id)

    custom_title = f"🐞 Bug Auto-Routed: #{task.id} {task.title}"
    custom_message = (
        f'Bug #{task.id} "{task.title}" [{task.priority}] has been automatically routed '
        f'and assigned to {assigned_engineer.username or assigned_engineer.name}.'
    )

    notifs = dispatch_event(
        event_type=EVENT_BUG_ROUTED,
        task=task,
        actor_id=actor_id,
        recipient_ids=recipients,
        priority=priority_level,
        custom_title=custom_title,
        custom_message=custom_message
    )

    if is_urgent:
        dispatch_event(
            event_type=EVENT_HIGH_PRIORITY_BUG,
            task=task,
            actor_id=actor_id,
            recipient_ids=recipients,
            priority="Urgent"
        )

    return notifs


def notify_unblocked_dependents(completed_task):
    """
    Finds all active tasks blocked by completed_task and alerts their owners:
    'Your deliverable is now unblocked!'
    """
    if not completed_task or not completed_task.id:
        return []

    try:
        # Find tasks where blocked_by_id == completed_task.id and not completed
        dependent_tasks = Task.query.filter(
            Task.blocked_by_id == completed_task.id,
            Task.completed.is_(False),
            Task.status != "Completed"
        ).all()

        notifications_sent = []
        for dep in dependent_tasks:
            recipients = set()
            if dep.assigned_to_id:
                recipients.add(dep.assigned_to_id)
            if dep.user_id:
                recipients.add(dep.user_id)
            if dep.created_by_id:
                recipients.add(dep.created_by_id)
            recipients.update(get_task_watchers(dep.id))

            n = dispatch_event(
                event_type=EVENT_BLOCKER_RESOLVED,
                task=dep,
                actor_id=None,
                recipient_ids=recipients,
                priority="Normal",
                metadata={"blocker_title": completed_task.title}
            )
            notifications_sent.extend(n)

        return notifications_sent
    except Exception as e:
        logger.error(f"Error notifying unblocked dependents for task {completed_task.id}: {e}")
        return []


def notify_task_assigned(task, new_assignee_id, former_assignee_id=None, actor_id=None):
    """Alerts new assignee, former assignee (if reassigned), and registered watchers."""
    if not task:
        return []

    notifications = []
    actor = db.session.get(User, actor_id) if actor_id else None
    actor_name = actor.username or actor.name if actor else "Team Lead"

    # Auto-subscribe new assignee to task
    if new_assignee_id:
        add_watcher(task.id, new_assignee_id)

    # 1. Alert new assignee
    if new_assignee_id and new_assignee_id != actor_id:
        n = dispatch_event(
            event_type=EVENT_TASK_ASSIGNED,
            task=task,
            actor_id=actor_id,
            recipient_ids=[new_assignee_id],
            custom_title=f"Assigned: {task.title}",
            custom_message=f'You have been assigned to deliverable "{task.title}" by {actor_name}.'
        )
        notifications.extend(n)

    # 2. Alert former assignee if reassigned
    if former_assignee_id and former_assignee_id != new_assignee_id and former_assignee_id != actor_id:
        n = dispatch_event(
            event_type=EVENT_TASK_ASSIGNED,
            task=task,
            actor_id=actor_id,
            recipient_ids=[former_assignee_id],
            custom_title=f"Reassigned: {task.title}",
            custom_message=f'Deliverable "{task.title}" has been reassigned to another engineer by {actor_name}.'
        )
        notifications.extend(n)

    # 3. Notify watchers
    watchers = set(get_task_watchers(task.id))
    watchers.discard(new_assignee_id)
    if former_assignee_id:
        watchers.discard(former_assignee_id)
    if actor_id:
        watchers.discard(actor_id)

    if watchers:
        n = dispatch_event(
            event_type=EVENT_TASK_ASSIGNED,
            task=task,
            actor_id=actor_id,
            recipient_ids=watchers,
            custom_title=f"Assignment Update: {task.title}",
            custom_message=f'Deliverable "{task.title}" assignee updated by {actor_name}.'
        )
        notifications.extend(n)

    return notifications


def notify_review_requested(task, actor_id):
    """Alerts team lead when proof of work is submitted for review."""
    if not task:
        return []

    actor = db.session.get(User, actor_id) if actor_id else None
    actor_name = actor.username or actor.name if actor else "Engineer"

    recipients = set()
    if task.team_id:
        team = db.session.get(Team, task.team_id)
        if team and team.lead_id:
            recipients.add(team.lead_id)

    # Also include task creator if creator != actor
    if task.created_by_id:
        recipients.add(task.created_by_id)

    # Include watchers
    recipients.update(get_task_watchers(task.id))

    return dispatch_event(
        event_type=EVENT_REVIEW_REQUESTED,
        task=task,
        actor_id=actor_id,
        recipient_ids=recipients,
        custom_title=f"Review Requested: {task.title}",
        custom_message=f'{actor_name} submitted proof of work for deliverable "{task.title}" and requested review.'
    )


def notify_feedback_submitted(task, actor_id, action, feedback=""):
    """Alerts assignee and watchers when Team Lead reviews proof of work."""
    if not task:
        return []

    recipients = set()
    assignee_id = task.assigned_to_id or task.user_id
    if assignee_id:
        recipients.add(assignee_id)
    if task.created_by_id:
        recipients.add(task.created_by_id)
    recipients.update(get_task_watchers(task.id))

    notifs = dispatch_event(
        event_type=EVENT_FEEDBACK_SUBMITTED,
        task=task,
        actor_id=actor_id,
        recipient_ids=recipients,
        metadata={"review_action": action, "feedback": feedback}
    )

    if action == "approve":
        notify_unblocked_dependents(task)

    return notifs
