import os
from datetime import date, datetime, timezone
from flask import Blueprint, request, session, jsonify
from models import db, Task, User, Team
from utils.auth_decorators import login_required

assistant_bp = Blueprint("assistant", __name__)

def get_scoped_tasks(user):
    """Retrieve SQLite tasks scoped to current user's role and team."""
    query = Task.query
    if user.role == "Admin" or user.is_admin:
        return query.all()
    elif user.role == "Lead" and user.team_id:
        return query.filter(Task.team_id == user.team_id).all()
    elif user.team_id:
        return query.filter(Task.team_id == user.team_id).all()
    else:
        return query.filter(db.or_(
            Task.assigned_to_id == user.id,
            Task.user_id == user.id
        )).all()

def rule_based_response(query_text, tasks, user):
    """Fallback rule-based engine synthesizing live SQLite task context."""
    today = date.today()
    q_lower = query_text.lower().strip()

    # Overdue tasks
    overdue_tasks = []
    for t in tasks:
        if t.status != "Completed" and not t.completed and t.due_date:
            try:
                t_date = date.fromisoformat(t.due_date[:10])
                if t_date < today:
                    overdue_tasks.append(t)
            except (ValueError, TypeError):
                pass

    completed_tasks = [t for t in tasks if t.status == "Completed" or t.completed]
    in_review_tasks = [t for t in tasks if t.status == "In Review"]
    in_progress_tasks = [t for t in tasks if t.status == "In Progress"]
    pending_tasks = [t for t in tasks if t.status == "Pending"]
    total = len(tasks)
    pct = round((len(completed_tasks) / total) * 100) if total > 0 else 0

    # 1. Overdue query
    if any(k in q_lower for k in ["overdue", "late", "missed", "past due"]):
        if not overdue_tasks:
            return (
                "### ✅ No Overdue Tasks\n\n"
                "All team deliverables are currently on track! Keep up the great velocity.\n\n"
                f"- **Active Deliverables:** {len(in_progress_tasks) + len(pending_tasks)}\n"
                f"- **In Review:** {len(in_review_tasks)}\n"
                f"- **Completion Rate:** {pct}%"
            )
        lines = [f"### ⚠️ Overdue Deliverables ({len(overdue_tasks)} Found)\n"]
        lines.append("The following deliverables have passed their target completion date:\n")
        for t in overdue_tasks:
            assignee = t.assignee.username if t.assignee else "Unassigned"
            lines.append(f"- **#{t.id} {t.title}**\n  - Priority: `{t.priority}` | Due: **{t.due_date}** | Assignee: *{assignee}* | Status: `{t.status}`")
        lines.append("\n> **Recommendation:** Reprioritize or reallocate blockers to ensure sprint completion.")
        return "\n".join(lines)

    # 2. Summarize team progress
    if any(k in q_lower for k in ["summarize", "progress", "summary", "team's progress", "velocity"]):
        bottlenecks = []
        if len(in_review_tasks) >= 3:
            bottlenecks.append(f"{len(in_review_tasks)} deliverables pending review")
        if len(overdue_tasks) > 0:
            bottlenecks.append(f"{len(overdue_tasks)} overdue deliverables")

        bottleneck_str = ", ".join(bottlenecks) if bottlenecks else "None identified. Workflow is healthy."

        team_name = user.team.name if user.team else "All Engineering Teams"
        return (
            f"### 📊 Team Progress Summary: {team_name}\n\n"
            f"- **Sprint Completion Rate:** **{pct}%** ({len(completed_tasks)}/{total} items completed)\n"
            f"- **Work In Progress:** **{len(in_progress_tasks)}** items active\n"
            f"- **Awaiting Lead Review:** **{len(in_review_tasks)}** items queued\n"
            f"- **Backlog / Pending:** **{len(pending_tasks)}** items\n"
            f"- **Overdue Critical Path:** **{len(overdue_tasks)}** items\n\n"
            f"#### 🔍 Bottleneck Analysis\n"
            f"- **Status:** {bottleneck_str}\n\n"
            f"> **Next Steps:** Prioritize closing items currently in review to unblock dependent architectural tracks."
        )

    # 3. Weekly status report
    if any(k in q_lower for k in ["weekly", "report", "sprint report", "status report", "draft"]):
        team_name = user.team.name if user.team else "Core Engineering"
        recent_done = completed_tasks[:4]
        in_flight = (in_progress_tasks + in_review_tasks)[:4]

        report = [
            f"# 📋 Weekly Engineering Status Report — {team_name}",
            f"**Generated:** {today.strftime('%B %d, %Y')} | **Reporting Period:** Current Sprint\n",
            "## 1. Executive Summary",
            f"During this cycle, the squad achieved an overall delivery rate of **{pct}%** across {total} tracked tickets.",
            f"Currently, **{len(in_progress_tasks)}** tickets are under active development and **{len(in_review_tasks)}** are in code review.\n",
            "## 2. Key Accomplishments & Deliverables Closed",
        ]
        if recent_done:
            for t in recent_done:
                report.append(f"- **{t.title}** ({t.category}) — *Completed*")
        else:
            report.append("- No tickets were closed in the selected interval.")

        report.append("\n## 3. In-Flight Focus & Reviews")
        if in_flight:
            for t in in_flight:
                assignee = t.assignee.username if t.assignee else "Team"
                report.append(f"- **{t.title}** — Assignee: *{assignee}* | Status: `{t.status}` ({t.priority} Priority)")
        else:
            report.append("- No active in-flight deliverables.")

        report.append("\n## 4. Risks & Overdue Blockers")
        if overdue_tasks:
            for t in overdue_tasks:
                report.append(f"- ⚠️ **{t.title}** due on {t.due_date} requires immediate attention.")
        else:
            report.append("- Zero blockers identified. All targets tracking on or ahead of schedule.")

        report.append("\n## 5. Objectives for Next Sprint")
        report.append("- Finalize open review tickets and run end-to-end integration tests.")
        report.append("- Begin technical discovery on upcoming architectural milestones.")
        return "\n".join(report)

    # 4. Break deliverable into subtasks
    if any(k in q_lower for k in ["break", "subtask", "smaller", "sub-task", "decomposition"]):
        # Find active or first available task for context
        ref_task = (in_progress_tasks or pending_tasks or tasks or [None])[0]
        context_name = f'"{ref_task.title}"' if ref_task else "Core Architectural Deliverable"
        return (
            f"### 🔨 Structured Architectural Subtasks for {context_name}\n\n"
            f"Here is a recommended 5-phase breakdown designed for maintainability and automated verification:\n\n"
            f"1. **Phase 1: Architecture Specification & API Contract Design**\n"
            f"   - Define RESTful schema, payloads, and role authorization headers.\n"
            f"   - Estimated Effort: 0.5 Day | Priority: `High`\n\n"
            f"2. **Phase 2: Database Migration & ORM Entity Modeling**\n"
            f"   - Write SQLAlchemy models, foreign key relationships, and indexes.\n"
            f"   - Estimated Effort: 1 Day | Priority: `High`\n\n"
            f"3. **Phase 3: Core Service Implementation & Business Logic**\n"
            f"   - Implement backend route handlers, transaction validation, and error guards.\n"
            f"   - Estimated Effort: 2 Days | Priority: `Medium`\n\n"
            f"4. **Phase 4: Frontend Component Integration & State Wiring**\n"
            f"   - Create responsive UI elements, dynamic event listeners, and API fetch wrappers.\n"
            f"   - Estimated Effort: 1.5 Days | Priority: `Medium`\n\n"
            f"5. **Phase 5: Automated Testing, Security Review & Performance Optimization**\n"
            f"   - Execute integration test cases, verify SQL query indexes, and submit proof of work.\n"
            f"   - Estimated Effort: 1 Day | Priority: `High`\n\n"
            f"> **Pro-Tip:** Each phase can be assigned to different squad engineers to parallelize delivery."
        )

    # 5. Default intelligent assistant overview
    highest_priority = [t for t in (in_progress_tasks + pending_tasks) if t.priority in ("Critical", "High")]
    next_up = highest_priority[0] if highest_priority else (in_progress_tasks or pending_tasks or [None])[0]

    return (
        f"### 🤖 Productivity Intelligence Insights\n\n"
        f"Hello **{user.username}**! Here is your live squad overview:\n\n"
        f"- **Total Workspace Tasks:** {total}\n"
        f"- **Completion Rate:** {pct}%\n"
        f"- **Overdue Items:** {len(overdue_tasks)}\n"
        f"- **Active In Progress:** {len(in_progress_tasks)}\n\n"
        + (f"**Recommended Next Action:** Focus on **'{next_up.title}'** (`{next_up.priority}` priority, due {next_up.due_date or 'soon'}).\n\n" if next_up else "")
        + "You can ask me to:\n"
        "- *Which tasks are overdue?*\n"
        "- *Summarize our team's progress.*\n"
        "- *Draft a weekly status report.*\n"
        "- *Break this deliverable into smaller subtasks.*"
    )

@assistant_bp.post("/query")
@login_required
def assistant_query():
    """
    Dual-engine AI Productivity Assistant endpoint.
    If GEMINI_API_KEY is configured, uses google-genai to synthesize contextual answers using live SQLite task state.
    Otherwise or on error, falls back to the Rule-Based Engine.
    """
    user_id = session.get("user_id")
    user = db.session.get(User, user_id)
    if not user:
        return jsonify(error="Authentication required"), 401

    data = request.get_json(silent=True) or {}
    query_text = (data.get("query") or data.get("prompt") or "").strip()
    if not query_text:
        return jsonify(error="Query prompt cannot be empty."), 400

    tasks = get_scoped_tasks(user)

    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)

            # Build compact live context from SQLite
            task_summaries = []
            for t in tasks[:30]:
                assignee = t.assignee.username if t.assignee else "Unassigned"
                task_summaries.append(
                    f"ID:{t.id} | '{t.title}' | Status:{t.status} | Priority:{t.priority} | Due:{t.due_date} | Assignee:{assignee}"
                )
            context_str = "\n".join(task_summaries)

            system_instruction = (
                f"You are the Taskflow AI Productivity Assistant for an enterprise engineering team. "
                f"The user is {user.username} (Role: {user.role}, Team: {user.team.name if user.team else 'General'}).\n"
                f"Here is the current live SQLite task dataset:\n{context_str}\n\n"
                f"Provide concise, professional markdown responses with clear bullet points, actionable recommendations, and formatted task references. "
                f"Never make up imaginary task IDs."
            )

            prompt = f"{system_instruction}\n\nUser Question: {query_text}"
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )

            if response and response.text:
                return jsonify({
                    "response": response.text,
                    "source": "ai",
                    "model_badge": "🤖 AI-Generated"
                }), 200
        except Exception:
            # Fall through to rule-based engine on any error (quota, network, etc.)
            pass

    # Rule-based fallback engine
    rule_output = rule_based_response(query_text, tasks, user)
    return jsonify({
        "response": rule_output,
        "source": "rule_based",
        "model_badge": "⚡ Rule-Based Summary"
    }), 200
