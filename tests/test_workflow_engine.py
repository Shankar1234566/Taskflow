"""
Unit Tests for Workflow Engine, Guardrails, and Cycle Detection.
"""
import pytest
from services.workflow import (
    WorkflowState, TriggerType, GuardCondition, WorkflowTransition,
    WorkflowStep, WorkflowPipelineDefinition, build_default_enterprise_pipeline,
    WorkflowEngine, WorkflowExecutionContext, detect_cycles, topological_sort,
    WorkflowValidator
)


def test_default_pipeline_initialization():
    pipe = build_default_enterprise_pipeline()
    assert pipe.initial_state == WorkflowState.BACKLOG
    assert WorkflowState.COMPLETED in pipe.terminal_states
    assert len(pipe.transitions) >= 6


def test_guard_condition_evaluation():
    guard = GuardCondition("Blocker Check", "blocker_reason", "is_not_empty", True, "Blocker reason required")
    assert not guard.evaluate({"blocker_reason": ""})
    assert guard.evaluate({"blocker_reason": "Waiting on API contract"})


def test_workflow_state_transition():
    engine = WorkflowEngine()
    ctx = WorkflowExecutionContext(
        task_id=101,
        current_state=WorkflowState.BACKLOG,
        initiator_id=1,
        initiator_role="Lead",
        attributes={"assigned_to_id": 2}
    )

    res = engine.transition(ctx, WorkflowState.TODO)
    assert res.success is True
    assert ctx.current_state == WorkflowState.TODO


def test_transition_guard_rejection():
    engine = WorkflowEngine()
    ctx = WorkflowExecutionContext(
        task_id=102,
        current_state=WorkflowState.IN_PROGRESS,
        initiator_id=3,
        initiator_role="Member",
        attributes={}  # Missing submission notes
    )

    res = engine.transition(ctx, WorkflowState.IN_REVIEW, trigger=TriggerType.REVIEW_SUBMITTED)
    assert res.success is False
    assert "submission_notes" in res.error_message


def test_cycle_detection_in_dag():
    # Valid DAG
    steps = [
        WorkflowStep("A", "Step A", "", WorkflowState.TODO, dependencies=[]),
        WorkflowStep("B", "Step B", "", WorkflowState.IN_PROGRESS, dependencies=["A"]),
        WorkflowStep("C", "Step C", "", WorkflowState.COMPLETED, dependencies=["B"])
    ]
    has_cycle, _ = detect_cycles(steps)
    assert has_cycle is False

    ok, order = topological_sort(steps)
    assert ok is True
    assert order == ["A", "B", "C"]

    # Cyclic graph
    cyclic_steps = [
        WorkflowStep("X", "Step X", "", WorkflowState.TODO, dependencies=["Z"]),
        WorkflowStep("Y", "Step Y", "", WorkflowState.IN_PROGRESS, dependencies=["X"]),
        WorkflowStep("Z", "Step Z", "", WorkflowState.COMPLETED, dependencies=["Y"])
    ]
    has_cycle_2, cycles = detect_cycles(cyclic_steps)
    assert has_cycle_2 is True
    assert len(cycles) > 0
