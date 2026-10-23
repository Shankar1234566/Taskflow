"""
Role-Based and Attribute-Based Access Control (RBAC/ABAC) Engine.
Enforces permissions, role inheritance hierarchies, and resource ownership checks.
"""
from .permissions import Permission, RolePermissionMatrix
from .policy_engine import RBACPolicyEngine, AccessRequest, AccessDecision

__all__ = ["Permission", "RolePermissionMatrix", "RBACPolicyEngine", "AccessRequest", "AccessDecision"]
