"""
Team Workload Distribution, Capacity Balancing, and Overload Detection Engine.
Calculates individual engineer allocations, flags burn-out risks, and recommends task shifts.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any


@dataclass
class MemberCapacity:
    """Represents an individual team member's allocated workload and available bandwidth."""
    user_id: int
    name: str
    email: str
    role: str
    team_id: Optional[int]
    total_assigned_tasks: int
    in_progress_tasks: int
    overdue_tasks: int
    estimated_hours_total: float
    max_weekly_capacity_hours: float = 40.0

    @property
    def utilization_percentage(self) -> float:
        """Percentage of weekly capacity utilized."""
        if self.max_weekly_capacity_hours <= 0:
            return 0.0
        return round((self.estimated_hours_total / self.max_weekly_capacity_hours) * 100, 2)

    @property
    def is_overloaded(self) -> bool:
        """Member has exceeded 100% capacity or has excessive concurrent items."""
        return self.utilization_percentage > 100.0 or self.in_progress_tasks >= 5


@dataclass
class ReallocationSuggestion:
    """Actionable recommendation to transfer a task from an overloaded member to an available one."""
    task_id: int
    task_title: str
    estimated_hours: float
    from_user_id: int
    from_user_name: str
    to_user_id: int
    to_user_name: str
    rationale: str


@dataclass
class WorkloadBalanceResult:
    """Complete summary of team capacity health and suggested optimizations."""
    team_id: Optional[int]
    total_members: int
    overloaded_members_count: int
    average_utilization_percent: float
    member_capacities: List[MemberCapacity]
    suggestions: List[ReallocationSuggestion] = field(default_factory=list)


class WorkloadAnalyzer:
    """Evaluates team assignments and balances work across available engineers."""

    @staticmethod
    def analyze_team(
        team_id: Optional[int],
        users: List[Dict[str, Any]],
        tasks: List[Dict[str, Any]],
        weekly_capacity_hours: float = 40.0
    ) -> WorkloadBalanceResult:
        """Compute individual capacities and derive reallocation recommendations."""
        member_map: Dict[int, MemberCapacity] = {}

        for u in users:
            uid = u["id"]
            member_map[uid] = MemberCapacity(
                user_id=uid,
                name=u.get("username") or u.get("name") or f"User-{uid}",
                email=u.get("email", ""),
                role=u.get("role", "Member"),
                team_id=u.get("team_id"),
                total_assigned_tasks=0,
                in_progress_tasks=0,
                overdue_tasks=0,
                estimated_hours_total=0.0,
                max_weekly_capacity_hours=weekly_capacity_hours
            )

        unassigned_tasks = []

        # Tally active task metrics
        for t in tasks:
            status = t.get("status", "Pending")
            if status in ("Completed", "Archived"):
                continue

            assignee_id = t.get("assigned_to_id") or t.get("user_id")
            hours = float(t.get("estimated_hours") or 4.0)

            if assignee_id and assignee_id in member_map:
                mem = member_map[assignee_id]
                mem.total_assigned_tasks += 1
                mem.estimated_hours_total += hours
                if status == "In Progress":
                    mem.in_progress_tasks += 1
                if t.get("is_overdue"):
                    mem.overdue_tasks += 1
            else:
                unassigned_tasks.append(t)

        members = list(member_map.values())
        overloaded = [m for m in members if m.is_overloaded]

        avg_util = 0.0
        if members:
            avg_util = round(sum(m.utilization_percentage for m in members) / len(members), 2)

        # Generate rebalancing suggestions
        suggestions: List[ReallocationSuggestion] = []
        underutilized = sorted([m for m in members if m.utilization_percentage < 70.0], key=lambda x: x.utilization_percentage)

        for over in overloaded:
            if not underutilized:
                break
            excess_hours = over.estimated_hours_total - over.max_weekly_capacity_hours
            target_receiver = underutilized[0]

            suggestions.append(ReallocationSuggestion(
                task_id=0,  # Generic proposal
                task_title="Rebalance lowest priority queued ticket",
                estimated_hours=min(8.0, max(2.0, excess_hours)),
                from_user_id=over.user_id,
                from_user_name=over.name,
                to_user_id=target_receiver.user_id,
                to_user_name=target_receiver.name,
                rationale=f"Transfer load from {over.name} ({over.utilization_percentage}% utilized) to {target_receiver.name} ({target_receiver.utilization_percentage}% utilized)."
            ))

        return WorkloadBalanceResult(
            team_id=team_id,
            total_members=len(members),
            overloaded_members_count=len(overloaded),
            average_utilization_percent=avg_util,
            member_capacities=members,
            suggestions=suggestions
        )
