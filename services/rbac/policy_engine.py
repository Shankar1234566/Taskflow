"""
Attribute-Based Policy Evaluation Engine (ABAC / RBAC).
Considers user role, resource ownership, team boundary scoping, and environment conditions.
"""
from dataclasses import dataclass
from typing import Dict, Optional, Any
from .permissions import Permission, RolePermissionMatrix


@dataclass
class AccessRequest:
    user_id: int
    user_role: str
    user_team_id: Optional[int]
    is_admin: bool
    permission: Permission
    resource: Optional[Dict[str, Any]] = None


@dataclass
class AccessDecision:
    granted: bool
    reason: str


class RBACPolicyEngine:
    """Evaluates access requests against organizational security policies."""

    @classmethod
    def evaluate(cls, req: AccessRequest) -> AccessDecision:
        # 1. Super-admin override
        if req.is_admin or req.user_role == "Admin":
            return AccessDecision(True, "Access granted via Administrator privileges.")

        # 2. Check role permission matrix
        allowed_perms = RolePermissionMatrix.get_permissions_for_role(req.user_role)
        if req.permission not in allowed_perms:
            return AccessDecision(False, f"Role '{req.user_role}' lacks permission '{req.permission.value}'.")

        # 3. Check ownership and team-scoping if resource is provided
        if req.resource:
            res_team_id = req.resource.get("team_id")
            res_owner_id = req.resource.get("assigned_to_id") or req.resource.get("user_id")

            # Leads can manage anything in their own team
            if req.user_role == "Lead":
                if res_team_id and req.user_team_id and res_team_id != req.user_team_id:
                    return AccessDecision(False, "Team Leads can only manage resources within their own team.")
                return AccessDecision(True, "Granted via Team Lead authority.")

            # Members can only delete or approve their own tickets
            if req.permission in (Permission.TASK_DELETE, Permission.TASK_APPROVE):
                if res_owner_id and res_owner_id != req.user_id:
                    return AccessDecision(False, "Regular members cannot delete or approve items owned by others.")

        return AccessDecision(True, "Granted by standard role authorization.")
