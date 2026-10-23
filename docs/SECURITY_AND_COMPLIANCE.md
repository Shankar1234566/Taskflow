# Taskflow Pro — Security, Governance & Compliance Guide

## 1. Security Architecture & Threat Model
Taskflow Pro enforces defense-in-depth across multiple operational layers:
- **Transport Security**: Requires TLS 1.3 in production environments with `Strict-Transport-Security` headers.
- **Session Authentication**: Secure HTTP-Only session cookies with `SameSite=Lax` prevent Cross-Site Scripting (XSS) and Cross-Site Request Forgery (CSRF).
- **Password Hashing**: Passwords hashed using bcrypt or PBKDF2 with HMAC-SHA256 (Werkzeug security).
- **SQL Injection Prevention**: 100% parameterization via SQLAlchemy ORM queries; zero raw string interpolation.

## 2. Role-Based Access Control (RBAC) Matrix
| Permission | Administrator | Team Lead | Member (IC) |
| :--- | :---: | :---: | :---: |
| Global System Metrics | Yes | No | No |
| User Provisioning & Demotion | Yes | No | No |
| Create & Delegate Tasks | Yes | Yes | Yes |
| Approve Work & Code Reviews | Yes | Yes | No |
| Clear Audit Logs | Yes | No | No |
| Cross-Team Task Inspection | Yes | Team Scoped | Team Scoped |

## 3. Compliance Controls (SOC2 / GDPR)
- **Immutable Audit Trails**: Every task creation, status transition, assignment, and deletion produces an activity log with actor ID and timestamp.
- **Data Minimization**: User profiles only capture essential identity attributes (`username`, `email`, `role`).
- **Cryptographic Hash Verification**: Audit logs are verifiable using chained SHA-256 hashes to guarantee tamper detection.
