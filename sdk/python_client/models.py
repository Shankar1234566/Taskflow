"""
Strongly-Typed Data Models for Taskflow SDK.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class UserModel:
    id: int
    username: str
    email: str
    role: str = "Member"
    is_admin: bool = False
    team_id: Optional[int] = None
    created_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserModel":
        return cls(
            id=data.get("id", 0),
            username=data.get("username") or data.get("name") or "",
            email=data.get("email", ""),
            role=data.get("role", "Member"),
            is_admin=bool(data.get("is_admin", False)),
            team_id=data.get("team_id"),
            created_at=data.get("created_at")
        )


@dataclass
class TeamModel:
    id: int
    name: str
    lead_id: Optional[int] = None
    created_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TeamModel":
        return cls(
            id=data.get("id", 0),
            name=data.get("name", ""),
            lead_id=data.get("lead_id"),
            created_at=data.get("created_at")
        )


@dataclass
class TaskModel:
    id: int
    title: str
    description: str = ""
    category: str = "General"
    priority: str = "Medium"
    status: str = "Pending"
    due_date: Optional[str] = None
    due_time: Optional[str] = None
    tags: str = ""
    is_starred: bool = False
    completed: bool = False
    team_id: Optional[int] = None
    created_by_id: Optional[int] = None
    assigned_to_id: Optional[int] = None
    submission_notes: Optional[str] = None
    git_repo_link: Optional[str] = None
    feedback_notes: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskModel":
        return cls(
            id=data.get("id", 0),
            title=data.get("title", ""),
            description=data.get("description", ""),
            category=data.get("category", "General"),
            priority=data.get("priority", "Medium"),
            status=data.get("status", "Pending"),
            due_date=data.get("due_date"),
            due_time=data.get("due_time"),
            tags=data.get("tags", ""),
            is_starred=bool(data.get("is_starred", False)),
            completed=bool(data.get("completed", False)),
            team_id=data.get("team_id"),
            created_by_id=data.get("created_by_id"),
            assigned_to_id=data.get("assigned_to_id"),
            submission_notes=data.get("submission_notes"),
            git_repo_link=data.get("git_repo_link"),
            feedback_notes=data.get("feedback_notes")
        )


@dataclass
class DashboardStatsModel:
    total: int = 0
    pending: int = 0
    in_progress: int = 0
    in_review: int = 0
    completed: int = 0
    overdue: int = 0
    starred: int = 0
    completion_percentage: float = 0.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DashboardStatsModel":
        return cls(
            total=data.get("total", 0),
            pending=data.get("pending", 0),
            in_progress=data.get("in_progress", 0),
            in_review=data.get("in_review", 0),
            completed=data.get("completed", 0),
            overdue=data.get("overdue", 0),
            starred=data.get("starred", 0),
            completion_percentage=float(data.get("completion_percentage") or data.get("percent_complete") or 0.0)
        )
