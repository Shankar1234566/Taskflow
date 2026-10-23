"""
Fine-Grained Enterprise Permission Enums and Matrices.
Covers task operations, team scoping, user management, and administrative privileges.
"""
from enum import Enum
from typing import Dict, Set


class Permission(str, Enum):
    # Task permissions
    TASK_CREATE = "task:create"
    TASK_READ = "task:read"
    TASK_UPDATE = "task:update"
    TASK_DELETE = "task:delete"
    TASK_ASSIGN = "task:assign"
    TASK_APPROVE = "task:approve"
    TASK_EXPORT = "task:export"

    # Team permissions
    TEAM_CREATE = "team:create"
    TEAM_MANAGE = "team:manage"
    TEAM_READ = "team:read"

    # Admin permissions
    ADMIN_PORTAL = "admin:portal"
    ADMIN_USERS_MANAGE = "admin:users_manage"
    ADMIN_AUDIT_VIEW = "admin:audit_view"


class RolePermissionMatrix:
    """Standard permission mapping across default enterprise personas."""

    ROLE_PERMISSIONS: Dict[str, Set[Permission]] = {
        "Admin": set(Permission),  # Full access
        "Lead": {
            Permission.TASK_CREATE,
            Permission.TASK_READ,
            Permission.TASK_UPDATE,
            Permission.TASK_DELETE,
            Permission.TASK_ASSIGN,
            Permission.TASK_APPROVE,
            Permission.TASK_EXPORT,
            Permission.TEAM_READ,
            Permission.TEAM_MANAGE,
            Permission.ADMIN_AUDIT_VIEW
        },
        "Member": {
            Permission.TASK_CREATE,
            Permission.TASK_READ,
            Permission.TASK_UPDATE,
            Permission.TASK_EXPORT,
            Permission.TEAM_READ
        }
    }

    @classmethod
    def get_permissions_for_role(cls, role: str) -> Set[Permission]:
        return cls.ROLE_PERMISSIONS.get(role, set())
