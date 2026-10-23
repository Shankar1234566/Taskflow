"""
Unit Tests for RBAC Policy Engine and Cryptographic Audit Logger.
"""
from services.rbac import RBACPolicyEngine, AccessRequest, Permission
from services.audit import CryptographicAuditLogger, ComplianceAuditor


def test_rbac_admin_override():
    req = AccessRequest(
        user_id=1,
        user_role="Admin",
        user_team_id=None,
        is_admin=True,
        permission=Permission.ADMIN_PORTAL
    )
    decision = RBACPolicyEngine.evaluate(req)
    assert decision.granted is True


def test_rbac_member_permission_denial():
    req = AccessRequest(
        user_id=4,
        user_role="Member",
        user_team_id=1,
        is_admin=False,
        permission=Permission.ADMIN_PORTAL
    )
    decision = RBACPolicyEngine.evaluate(req)
    assert decision.granted is False


def test_cryptographic_audit_logger():
    logger = CryptographicAuditLogger()
    e1 = logger.log(1, "CREATE", "Task:1", {"title": "Task 1"})
    e2 = logger.log(1, "UPDATE", "Task:1", {"title": "Task 1 Updated"})

    assert e1.previous_hash == logger.GENESIS_HASH
    assert e2.previous_hash == e1.current_hash

    is_valid, _ = logger.verify_integrity()
    assert is_valid is True
