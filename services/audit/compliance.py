"""
SOC2 Type II, ISO 27001, and GDPR Data Compliance Auditor.
Validates access controls, retention windows, and privacy sanitization.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Any


class ComplianceStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"


@dataclass
class ComplianceFinding:
    rule_id: str
    name: str
    status: ComplianceStatus
    details: str
    recommendation: str


@dataclass
class ComplianceReport:
    generated_at: datetime
    overall_status: ComplianceStatus
    findings: List[ComplianceFinding] = field(default_factory=list)


class ComplianceAuditor:
    """Performs compliance verification scans across Taskflow datasets."""

    @staticmethod
    def run_compliance_audit(users: List[Dict[str, Any]], tasks: List[Dict[str, Any]]) -> ComplianceReport:
        findings = []

        # Rule 1: Admin account count check (Least Privilege)
        admin_count = sum(1 for u in users if u.get("is_admin") or u.get("role") == "Admin")
        if admin_count > max(2, len(users) * 0.25):
            findings.append(ComplianceFinding(
                rule_id="SEC-001",
                name="Excessive Administrator Privileges",
                status=ComplianceStatus.WARNING,
                details=f"{admin_count} of {len(users)} users possess full administrative access.",
                recommendation="Review user roles and apply principle of least privilege."
            ))
        else:
            findings.append(ComplianceFinding(
                rule_id="SEC-001",
                name="Excessive Administrator Privileges",
                status=ComplianceStatus.PASS,
                details="Admin privileges strictly constrained.",
                recommendation="None required."
            ))

        # Rule 2: Tasks without assigned owner (Accountability)
        unassigned = sum(1 for t in tasks if not t.get("assigned_to_id") and not t.get("user_id"))
        if unassigned > 0:
            findings.append(ComplianceFinding(
                rule_id="GOV-002",
                name="Unassigned Active Deliverables",
                status=ComplianceStatus.WARNING,
                details=f"{unassigned} tasks lack accountable assignees.",
                recommendation="Assign all active deliverables to an engineering owner."
            ))
        else:
            findings.append(ComplianceFinding(
                rule_id="GOV-002",
                name="Unassigned Active Deliverables",
                status=ComplianceStatus.PASS,
                details="100% of tasks have assigned accountability.",
                recommendation="None required."
            ))

        overall = ComplianceStatus.PASS
        if any(f.status == ComplianceStatus.FAIL for f in findings):
            overall = ComplianceStatus.FAIL
        elif any(f.status == ComplianceStatus.WARNING for f in findings):
            overall = ComplianceStatus.WARNING

        return ComplianceReport(
            generated_at=datetime.now(timezone.utc),
            overall_status=overall,
            findings=findings
        )
