"""
Unit Tests for CSV, JSON, and iCalendar Exporters and Batch Importer.
"""
from services.export_import import CSVExporter, JSONExporter, ICalExporter, BatchTaskImporter


def test_csv_export():
    tasks = [{"id": 1, "title": "Deploy API Gateway", "category": "DevOps", "priority": "High"}]
    csv_str = CSVExporter.export_tasks_to_csv(tasks)
    assert "Deploy API Gateway" in csv_str
    assert "id,title,description" in csv_str


def test_json_export():
    tasks = [{"id": 1, "title": "Database Optimization"}]
    json_str = JSONExporter.export_dataset(tasks, [], [])
    assert "Database Optimization" in json_str
    assert "checksum" in json_str


def test_ical_export():
    tasks = [{"id": 1, "title": "Sprint Milestone", "due_date": "2026-11-20"}]
    ical_str = ICalExporter.export_calendar_feed(tasks)
    assert "BEGIN:VCALENDAR" in ical_str
    assert "SUMMARY:[Medium] #1 Sprint Milestone" in ical_str


def test_batch_importer():
    csv_content = """title,priority,category\nDeploy K8s,Critical,Infrastructure\nFix Nav,Medium,Frontend"""
    res = BatchTaskImporter.parse_csv(csv_content)
    assert res.is_valid is True
    assert len(res.parsed_tasks) == 2
    assert res.parsed_tasks[0]["priority"] == "Critical"
