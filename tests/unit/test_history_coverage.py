import json

from scripts.ingest_history import _write_coverage_report


def test_write_coverage_report_creates_machine_readable_report(tmp_path):
    report = {"planned_chunks": 2, "chunks": [{"label": "year=2024"}]}

    report_path = _write_coverage_report(tmp_path / "history", report)

    assert report_path == tmp_path / "history" / "coverage_report.json"
    assert json.loads(report_path.read_text()) == report