"""
Workflow Validation, Cycle Detection, and Topological Dependency Analyzers.
Uses Tarjan's strongly connected components and Kahn's algorithm for DAG validation.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple

from .definitions import WorkflowStep, WorkflowPipelineDefinition, WorkflowState


@dataclass
class WorkflowValidationResult:
    """Encapsulates structural verification findings for a pipeline definition."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    topological_order: List[str] = field(default_factory=list)
    has_cycles: bool = False
    unreachable_states: List[WorkflowState] = field(default_factory=list)
    dead_end_states: List[WorkflowState] = field(default_factory=list)


def detect_cycles(steps: List[WorkflowStep]) -> Tuple[bool, List[List[str]]]:
    """
    Detects circular dependencies among steps using Tarjan's Strongly Connected Components algorithm.
    Returns (has_cycle, list_of_cycles).
    """
    adj: Dict[str, List[str]] = {s.step_id: list(s.dependencies) for s in steps}
    all_step_ids = set(adj.keys())

    # Verify all referenced dependencies exist
    for step_id, deps in adj.items():
        for d in deps:
            if d not in all_step_ids:
                return False, []

    index = 0
    stack: List[str] = []
    indices: Dict[str, int] = {}
    lowlinks: Dict[str, int] = {}
    on_stack: Set[str] = set()
    sccs: List[List[str]] = []

    def strongconnect(v: str):
        nonlocal index
        indices[v] = index
        lowlinks[v] = index
        index += 1
        stack.append(v)
        on_stack.add(v)

        for w in adj.get(v, []):
            if w not in indices:
                strongconnect(w)
                lowlinks[v] = min(lowlinks[v], lowlinks[w])
            elif w in on_stack:
                lowlinks[v] = min(lowlinks[v], indices[w])

        if lowlinks[v] == indices[v]:
            scc = []
            while True:
                w = stack.pop()
                on_stack.remove(w)
                scc.append(w)
                if w == v:
                    break
            if len(scc) > 1 or (scc and scc[0] in adj.get(scc[0], [])):
                sccs.append(scc)

    for node in all_step_ids:
        if node not in indices:
            strongconnect(node)

    return len(sccs) > 0, sccs


def topological_sort(steps: List[WorkflowStep]) -> Tuple[bool, List[str]]:
    """
    Computes a valid linear execution order for steps using Kahn's algorithm.
    Returns (success, ordered_step_ids).
    """
    step_map = {s.step_id: s for s in steps}
    in_degree: Dict[str, int] = {s.step_id: 0 for s in steps}
    graph: Dict[str, List[str]] = {s.step_id: [] for s in steps}

    for s in steps:
        for dep in s.dependencies:
            if dep in graph:
                graph[dep].append(s.step_id)
                in_degree[s.step_id] += 1
            else:
                return False, []

    queue = [sid for sid, deg in in_degree.items() if deg == 0]
    order = []

    while queue:
        curr = queue.pop(0)
        order.append(curr)
        for neighbor in graph[curr]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(order) != len(steps):
        return False, []
    return True, order


class WorkflowValidator:
    """Performs deep static analysis on workflow pipeline graphs."""

    @classmethod
    def validate_pipeline(cls, pipeline: WorkflowPipelineDefinition) -> WorkflowValidationResult:
        errors: List[str] = []
        warnings: List[str] = []

        # 1. Check initial state
        if not pipeline.initial_state:
            errors.append("Pipeline must have an initial_state defined.")

        # 2. Check terminal states
        if not pipeline.terminal_states:
            warnings.append("Pipeline has no terminal_states defined.")

        # 3. Analyze state reachability graph
        all_states = set(WorkflowState)
        reachable: Set[WorkflowState] = {pipeline.initial_state}
        frontier = [pipeline.initial_state]

        adj: Dict[WorkflowState, Set[WorkflowState]] = {st: set() for st in all_states}
        for t in pipeline.transitions:
            adj[t.from_state].add(t.to_state)

        while frontier:
            curr = frontier.pop(0)
            for nxt in adj.get(curr, set()):
                if nxt not in reachable:
                    reachable.add(nxt)
                    frontier.append(nxt)

        unreachable = [st for st in all_states if st not in reachable]

        # 4. Check for dead ends (states with no outgoing transitions that are not terminal)
        dead_ends = []
        for st in reachable:
            if st not in pipeline.terminal_states and len(adj.get(st, set())) == 0:
                dead_ends.append(st)
                errors.append(f"State '{st.value}' has no outgoing transitions but is not declared terminal.")

        # 5. Check step dependencies for cycles
        has_cycles = False
        top_order: List[str] = []
        if pipeline.steps:
            has_cycles, cycles = detect_cycles(pipeline.steps)
            if has_cycles:
                errors.append(f"Cycle detected in workflow steps: {cycles}")
            else:
                ok, order = topological_sort(pipeline.steps)
                if ok:
                    top_order = order
                else:
                    errors.append("Failed to resolve topological order for workflow steps.")

        is_valid = len(errors) == 0
        return WorkflowValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            topological_order=top_order,
            has_cycles=has_cycles,
            unreachable_states=unreachable,
            dead_end_states=dead_ends
        )
