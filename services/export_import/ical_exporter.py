"""
RFC 5545 iCalendar (ICS) Feed Generator.
Transforms task deadlines into standard calendar events compatible with Google Calendar and Apple Calendar.
"""
from datetime import date, datetime
from typing import Dict, List, Any


class ICalExporter:
    """Generates VCALENDAR / VEVENT payloads for deadline synchronization."""

    @classmethod
    def export_calendar_feed(cls, tasks: List[Dict[str, Any]], calendar_name: str = "Taskflow Deadlines") -> str:
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            f"PRODID:-//Taskflow Pro//Task Management//EN",
            f"X-WR-CALNAME:{calendar_name}",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH"
        ]

        for t in tasks:
            due_str = t.get("due_date")
            if not due_str:
                continue

            # Format YYYYMMDD
            clean_due = due_str[:10].replace("-", "")
            tid = t.get("id")
            title = t.get("title", "Deliverable")
            desc = t.get("description", "")
            prio = t.get("priority", "Medium")

            lines.extend([
                "BEGIN:VEVENT",
                f"UID:taskflow-{tid}@taskflow.local",
                f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
                f"DTSTART;VALUE=DATE:{clean_due}",
                f"DTEND;VALUE=DATE:{clean_due}",
                f"SUMMARY:[{prio}] #{tid} {title}",
                f"DESCRIPTION:{desc}",
                f"STATUS:CONFIRMED",
                "END:VEVENT"
            ])

        lines.append("END:VCALENDAR")
        return "\\r\\n".join(lines) + "\\r\\n"
