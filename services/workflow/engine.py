"""
Workflow Orchestration Engine and State Machine Execution Runtime.
Handles asynchronous task transitions, transaction isolation, action side-effects,
and state change hooks.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Callable, Tuple
import logging

from .definitions import (
    WorkflowState,
    TriggerType,
    ActionType,
    WorkflowAction,
    WorkflowTransition,
    WorkflowPipelineDefinition,
    build_default_enterprise_pipeline
)

logger = logging.getLogger("taskflow.services.workflow")


@dataclass
class WorkflowExecutionContext:
    """Encapsulates the runtime context for an active workflow execution."""
    task_id: int
    current_state: WorkflowState
    initiator_id: int
    initiator_role: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def update_attribute(self, key: str, value: Any) -> None:
        """Update a contextual property and log the mutation."""
        old_val = self.attributes.get(key)
        self.attributes[key] = value
        self.history.append({
            "action": "ATTRIBUTE_UPDATED",
            "key": key,
            "old_value": old_val,
            "new_value": value,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })


@dataclass
class ExecutionResult:
    """Outcome of a workflow transition attempt."""
    success: bool
    from_state: WorkflowState
    to_state: WorkflowState
    transition_name: Optional[str] = None
    error_message: Optional[str] = None
    executed_actions: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ActionHandlerRegistry:
    """Maintains hooks and custom executors for WorkflowAction types."""
    def __init__(self):
        self._handlers: Dict[ActionType, Callable[[WorkflowAction, WorkflowExecutionContext], bool]] = {}
        self._register_default_handlers()

    def register(self, action_type: ActionType, handler: Callable[[WorkflowAction, WorkflowExecutionContext], bool]) -> None:
        self._handlers[action_type] = handler

    def execute(self, action: WorkflowAction, context: WorkflowExecutionContext) -> bool:
        handler = self._handlers.get(action.action_type)
        if not handler:
            logger.warning(f"No handler registered for action type: {action.action_type}")
            return True
        try:
            return handler(action, context)
        except Exception as e:
            logger.error(f"Error executing action {action.action_type}: {e}", exc_info=True)
            return not action.is_critical

    def _register_default_handlers(self) -> None:
        def log_audit(act: WorkflowAction, ctx: WorkflowExecutionContext) -> bool:
            logger.info(f"[AUDIT] Task {ctx.task_id} transitioned. Details: {act.parameters}")
            return True

        def update_status(act: WorkflowAction, ctx: WorkflowExecutionContext) -> bool:
            new_state = act.parameters.get("target_state")
            if new_state:
                ctx.current_state = WorkflowState(new_state)
            return True

        def add_comment(act: WorkflowAction, ctx: WorkflowExecutionContext) -> bool:
            logger.info(f"[COMMENT] Task {ctx.task_id}: {act.parameters.get('comment_text', '')}")
            return True

        self.register(ActionType.LOG_AUDIT_ENTRY, log_audit)
        self.register(ActionType.UPDATE_STATUS, update_status)
        self.register(ActionType.ADD_COMMENT, add_comment)


class WorkflowEngine:
    """
    Primary workflow coordinator.
    Enforces RBAC permissions, guard logic, transition rules, and side-effect dispatching.
    """
    def __init__(self, pipeline: Optional[WorkflowPipelineDefinition] = None):
        self.pipeline = pipeline or build_default_enterprise_pipeline()
        self.action_registry = ActionHandlerRegistry()
        self._transition_listeners: List[Callable[[WorkflowExecutionContext, WorkflowTransition], None]] = []

    def add_transition_listener(self, listener: Callable[[WorkflowExecutionContext, WorkflowTransition], None]) -> None:
        self._transition_listeners.append(listener)

    def transition(
        self,
        context: WorkflowExecutionContext,
        target_state: WorkflowState,
        trigger: TriggerType = TriggerType.MANUAL
    ) -> ExecutionResult:
        """
        Executes a state transition from context.current_state to target_state.
        Evaluates guards, executes pre-actions, updates state, and runs post-actions.
        """
        current_state = context.current_state

        if current_state == target_state:
            return ExecutionResult(
                success=True,
                from_state=current_state,
                to_state=target_state,
                transition_name="NO_OP",
                error_message="Task is already in the requested state."
            )

        transition_rule = self.pipeline.get_transition(current_state, target_state)
        if not transition_rule:
            msg = f"Illegal transition from '{current_state.value}' to '{target_state.value}'. No rule defined."
            logger.warning(msg)
            return ExecutionResult(
                success=False,
                from_state=current_state,
                to_state=target_state,
                error_message=msg
            )

        # Check authorizations and guards
        allowed, reason = transition_rule.can_transition(context.initiator_role, context.attributes)
        if not allowed:
            logger.warning(f"Transition rejected for Task {context.task_id}: {reason}")
            return ExecutionResult(
                success=False,
                from_state=current_state,
                to_state=target_state,
                transition_name=transition_rule.name,
                error_message=reason
            )

        executed_actions = []

        # Execute pre-actions
        for act in transition_rule.pre_actions:
            ok = self.action_registry.execute(act, context)
            executed_actions.append(f"PRE:{act.action_type.value}")
            if not ok and act.is_critical:
                return ExecutionResult(
                    success=False,
                    from_state=current_state,
                    to_state=target_state,
                    transition_name=transition_rule.name,
                    error_message=f"Critical pre-action failed: {act.description or act.action_type.value}",
                    executed_actions=executed_actions
                )

        # Mutate state
        context.current_state = target_state
        context.history.append({
            "action": "STATE_TRANSITION",
            "from_state": current_state.value,
            "to_state": target_state.value,
            "initiator_id": context.initiator_id,
            "initiator_role": context.initiator_role,
            "transition_name": transition_rule.name,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        # Execute post-actions
        for act in transition_rule.post_actions:
            self.action_registry.execute(act, context)
            executed_actions.append(f"POST:{act.action_type.value}")

        # Notify external event subscribers
        for listener in self._transition_listeners:
            try:
                listener(context, transition_rule)
            except Exception as e:
                logger.error(f"Error in transition listener: {e}", exc_info=True)

        logger.info(f"Task {context.task_id} successfully transitioned {current_state.value} -> {target_state.value}")
        return ExecutionResult(
            success=True,
            from_state=current_state,
            to_state=target_state,
            transition_name=transition_rule.name,
            executed_actions=executed_actions
        )

    def can_transition(
        self,
        current_state: WorkflowState,
        target_state: WorkflowState,
        role: str,
        context_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Predictive inspection whether a transition would succeed without mutating state."""
        transition_rule = self.pipeline.get_transition(current_state, target_state)
        if not transition_rule:
            return False, f"No transition defined from {current_state.value} to {target_state.value}."
        return transition_rule.can_transition(role, context_data)
