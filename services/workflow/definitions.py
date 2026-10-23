"""
Workflow Definitions, Schemas, and Trigger Models.
Provides standard transitions, action types, guard condition models, and step payloads.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple


class WorkflowState(str, Enum):
    DRAFT = "DRAFT"
    BACKLOG = "BACKLOG"
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"
    CANCELLED = "CANCELLED"


class TriggerType(str, Enum):
    MANUAL = "MANUAL"
    STATUS_CHANGE = "STATUS_CHANGE"
    TIME_ELAPSED = "TIME_ELAPSED"
    SLA_BREACH = "SLA_BREACH"
    WEBHOOK_RECEIVED = "WEBHOOK_RECEIVED"
    REVIEW_SUBMITTED = "REVIEW_SUBMITTED"
    PR_MERGED = "PR_MERGED"


class ActionType(str, Enum):
    UPDATE_STATUS = "UPDATE_STATUS"
    ASSIGN_USER = "ASSIGN_USER"
    ASSIGN_TEAM = "ASSIGN_TEAM"
    SEND_NOTIFICATION = "SEND_NOTIFICATION"
    TRIGGER_WEBHOOK = "TRIGGER_WEBHOOK"
    LOG_AUDIT_ENTRY = "LOG_AUDIT_ENTRY"
    ADD_COMMENT = "ADD_COMMENT"
    SET_TAGS = "SET_TAGS"
    SET_PRIORITY = "SET_PRIORITY"


@dataclass
class GuardCondition:
    """Represents a rule that must evaluate to True before a step transition executes."""
    name: str
    attribute: str
    operator: str  # "eq", "neq", "in", "gt", "gte", "lt", "lte", "is_not_empty"
    expected_value: Any
    error_message: str

    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluates whether the context fulfills this condition."""
        val = context.get(self.attribute)
        if self.operator == "eq":
            return val == self.expected_value
        elif self.operator == "neq":
            return val != self.expected_value
        elif self.operator == "in":
            return val in self.expected_value if self.expected_value else False
        elif self.operator == "gt":
            return val is not None and val > self.expected_value
        elif self.operator == "gte":
            return val is not None and val >= self.expected_value
        elif self.operator == "lt":
            return val is not None and val < self.expected_value
        elif self.operator == "lte":
            return val is not None and val <= self.expected_value
        elif self.operator == "is_not_empty":
            return bool(val)
        return False


@dataclass
class WorkflowAction:
    """An action to execute when a workflow step or transition fires."""
    action_type: ActionType
    parameters: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    is_critical: bool = True
    retry_count: int = 3


@dataclass
class WorkflowTransition:
    """Defines an allowed state change between two WorkflowStates."""
    from_state: WorkflowState
    to_state: WorkflowState
    trigger: TriggerType
    name: str
    description: str = ""
    required_roles: List[str] = field(default_factory=list)
    guards: List[GuardCondition] = field(default_factory=list)
    pre_actions: List[WorkflowAction] = field(default_factory=list)
    post_actions: List[WorkflowAction] = field(default_factory=list)

    def can_transition(self, user_role: str, context: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Verify role authorization and evaluate all guard conditions."""
        if self.required_roles and user_role not in self.required_roles:
            return False, f"Role '{user_role}' is not authorized for transition '{self.name}'."
        for guard in self.guards:
            if not guard.evaluate(context):
                return False, f"Guard failure: {guard.error_message}"
        return True, None


@dataclass
class WorkflowStep:
    """A discrete unit of work within a larger workflow pipeline."""
    step_id: str
    title: str
    description: str
    target_state: WorkflowState
    estimated_hours: float = 1.0
    dependencies: List[str] = field(default_factory=list)
    required_inputs: List[str] = field(default_factory=list)
    output_schema: Dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 86400
    is_blocking: bool = True


@dataclass
class WorkflowPipelineDefinition:
    """Complete specification of a multi-step business workflow pipeline."""
    pipeline_id: str
    name: str
    version: str
    description: str
    initial_state: WorkflowState
    terminal_states: List[WorkflowState]
    transitions: List[WorkflowTransition] = field(default_factory=list)
    steps: List[WorkflowStep] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def get_transition(self, from_state: WorkflowState, to_state: WorkflowState) -> Optional[WorkflowTransition]:
        """Look up transition rule between two states."""
        for t in self.transitions:
            if t.from_state == from_state and t.to_state == to_state:
                return t
        return None

    def get_allowed_transitions(self, current_state: WorkflowState) -> List[WorkflowTransition]:
        """Return all legal transitions from the current state."""
        return [t for t in self.transitions if t.from_state == current_state]


def build_default_enterprise_pipeline() -> WorkflowPipelineDefinition:
    """Build the standard 6-state enterprise task lifecycle pipeline with guard rails."""
    transitions = [
        WorkflowTransition(
            from_state=WorkflowState.BACKLOG,
            to_state=WorkflowState.TODO,
            trigger=TriggerType.MANUAL,
            name="Sprint Triage & Allocation",
            description="Move from product backlog to sprint active board.",
            required_roles=["Admin", "Lead"],
            guards=[GuardCondition("Assignee Check", "assigned_to_id", "is_not_empty", True, "Task must have an assigned owner before sprint commit.")]
        ),
        WorkflowTransition(
            from_state=WorkflowState.TODO,
            to_state=WorkflowState.IN_PROGRESS,
            trigger=TriggerType.MANUAL,
            name="Commence Work",
            description="Developer marks task active.",
            required_roles=["Admin", "Lead", "Member"]
        ),
        WorkflowTransition(
            from_state=WorkflowState.IN_PROGRESS,
            to_state=WorkflowState.BLOCKED,
            trigger=TriggerType.MANUAL,
            name="Escalate Impediment",
            description="Flag task with blocker reason for management unblocking.",
            required_roles=["Admin", "Lead", "Member"],
            guards=[GuardCondition("Blocker Reason", "blocker_reason", "is_not_empty", True, "Must specify a reason for blocker flag.")]
        ),
        WorkflowTransition(
            from_state=WorkflowState.BLOCKED,
            to_state=WorkflowState.IN_PROGRESS,
            trigger=TriggerType.MANUAL,
            name="Unblock Deliverable",
            description="Clear blocker and resume execution.",
            required_roles=["Admin", "Lead"]
        ),
        WorkflowTransition(
            from_state=WorkflowState.IN_PROGRESS,
            to_state=WorkflowState.IN_REVIEW,
            trigger=TriggerType.REVIEW_SUBMITTED,
            name="Submit Deliverable for Review",
            description="Submit code proof of work or documentation for team lead signoff.",
            required_roles=["Admin", "Lead", "Member"],
            guards=[
                GuardCondition("Proof Notes", "submission_notes", "is_not_empty", True, "submission_notes or pull request link is required.")
            ]
        ),
        WorkflowTransition(
            from_state=WorkflowState.IN_REVIEW,
            to_state=WorkflowState.IN_PROGRESS,
            trigger=TriggerType.MANUAL,
            name="Request Revisions",
            description="Reviewer rejects deliverable with feedback for amendment.",
            required_roles=["Admin", "Lead"],
            guards=[GuardCondition("Feedback Provided", "feedback_notes", "is_not_empty", True, "Reviewer must provide feedback when requesting revisions.")]
        ),
        WorkflowTransition(
            from_state=WorkflowState.IN_REVIEW,
            to_state=WorkflowState.COMPLETED,
            trigger=TriggerType.MANUAL,
            name="Approve & Signoff",
            description="Final signoff from lead or administrator.",
            required_roles=["Admin", "Lead"]
        ),
        WorkflowTransition(
            from_state=WorkflowState.COMPLETED,
            to_state=WorkflowState.ARCHIVED,
            trigger=TriggerType.TIME_ELAPSED,
            name="Sprint Archive",
            description="Archive completed tasks after milestone close.",
            required_roles=["Admin"]
        )
    ]

    steps = [
        WorkflowStep("S1", "Requirement Discovery", "Verify ticket acceptance criteria and architectural bounds", WorkflowState.TODO, 2.0),
        WorkflowStep("S2", "Implementation & Unit Tests", "Author implementation code and unit test cases", WorkflowState.IN_PROGRESS, 8.0, ["S1"]),
        WorkflowStep("S3", "Peer Review & Verification", "Review submitted pull request and verify proof of work", WorkflowState.IN_REVIEW, 2.0, ["S2"]),
        WorkflowStep("S4", "Production Deployment", "Release verified deliverable to staging/production", WorkflowState.COMPLETED, 1.0, ["S3"])
    ]

    return WorkflowPipelineDefinition(
        pipeline_id="pipe_enterprise_v2",
        name="Enterprise Engineering Taskflow Pipeline",
        version="2.0.0",
        description="Rigorous multi-stage delivery pipeline ensuring accountability, code review, and compliance auditing.",
        initial_state=WorkflowState.BACKLOG,
        terminal_states=[WorkflowState.COMPLETED, WorkflowState.ARCHIVED, WorkflowState.CANCELLED],
        transitions=transitions,
        steps=steps,
        metadata={"sprint_cadence_days": 14, "requires_proof_of_work": True}
    )
