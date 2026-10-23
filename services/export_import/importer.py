"""
Universal Batch Task Importer with Dry-Run Validation and Rollback Guardrails.
Imports CSV/JSON data into Taskflow models safely.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Any
import csv
import io


@dataclass
class ImportValidationResult:
    is_valid: bool
    total_rows: int
    valid_rows: int
    errors: List[str] = field(default_factory=list)
    parsed_tasks: List[Dict[str, Any]] = field(default_factory=list)


class BatchTaskImporter:
    """Validates and parses bulk import payloads."""

    VALID_PRIORITIES = {"Critical", "High", "Medium", "Low"}
    VALID_STATUSES = {"Pending", "In Progress", "In Review", "Completed", "Blocked"}

    @classmethod
    def parse_csv(cls, csv_text: str) -> ImportValidationResult:
        errors = []
        parsed = []
        reader = csv.DictReader(io.StringIO(csv_text))

        row_num = 1
        for row in reader:
            row_num += 1
            title = (row.get("title") or "").strip()
            if not title:
                errors.append(f"Row {row_num}: Title is required.")
                continue

            priority = (row.get("priority") or "Medium").capitalize()
            if priority not in cls.VALID_PRIORITIES:
                priority = "Medium"

            status = (row.get("status") or "Pending").strip()
            if status not in cls.VALID_STATUSES:
                status = "Pending"

            parsed.append({
                "title": title,
                "description": row.get("description", ""),
                "category": row.get("category", "Imported"),
                "priority": priority,
                "status": status,
                "due_date": row.get("due_date", ""),
                "tags": row.get("tags", "batch-import")
            })

        return ImportValidationResult(
            is_valid=len(errors) == 0,
            total_rows=row_num - 1,
            valid_rows=len(parsed),
            errors=errors,
            parsed_tasks=parsed
        )
