"""Phase 1 acceptance: the generated sample dataset must be complete and consistent.

The dataset is committed, so this test validates committed files rather than
regenerating them. It checks:
  - row counts of emails.csv, leads.csv, tasks.csv
  - the presence of 5 meeting notes
  - required columns
  - GROUND_TRUTH.json maps every pattern to source IDs that actually exist
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "sample"
NOTES_DIR = DATA_DIR / "meeting_notes"

EXPECTED_EMAILS = 60
EXPECTED_LEADS = 30
EXPECTED_TASKS = 25
EXPECTED_NOTES = 5


def _read_csv(name: str) -> list[dict[str, str]]:
    with (DATA_DIR / name).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_emails_csv_exists_with_expected_count() -> None:
    rows = _read_csv("emails.csv")
    assert len(rows) == EXPECTED_EMAILS, f"expected {EXPECTED_EMAILS} emails, got {len(rows)}"


def test_emails_csv_has_required_columns() -> None:
    rows = _read_csv("emails.csv")
    required = {"id", "date", "from", "to", "subject", "body", "labels"}
    assert required.issubset(rows[0].keys()), f"missing columns: {required - set(rows[0].keys())}"


def test_leads_csv_exists_with_expected_count() -> None:
    rows = _read_csv("leads.csv")
    assert len(rows) == EXPECTED_LEADS, f"expected {EXPECTED_LEADS} leads, got {len(rows)}"


def test_leads_csv_has_required_columns() -> None:
    rows = _read_csv("leads.csv")
    required = {"id", "created", "company", "contact", "email", "source", "status"}
    assert required.issubset(rows[0].keys()), f"missing columns: {required - set(rows[0].keys())}"


def test_meeting_notes_count() -> None:
    notes = sorted(NOTES_DIR.glob("*.txt"))
    assert len(notes) == EXPECTED_NOTES, f"expected {EXPECTED_NOTES} notes, got {len(notes)}"


def test_tasks_csv_exists_with_expected_count() -> None:
    rows = _read_csv("tasks.csv")
    assert len(rows) == EXPECTED_TASKS, f"expected {EXPECTED_TASKS} tasks, got {len(rows)}"


def test_ground_truth_maps_patterns_to_real_ids() -> None:
    gt = json.loads((DATA_DIR / "GROUND_TRUTH.json").read_text(encoding="utf-8"))
    patterns = gt["patterns"]
    assert len(patterns) >= 3, "expected at least 3 hidden patterns"

    email_ids = {r["id"] for r in _read_csv("emails.csv")}
    lead_ids = {r["id"] for r in _read_csv("leads.csv")}
    task_ids = {r["id"] for r in _read_csv("tasks.csv")}
    note_ids = {p.stem for p in NOTES_DIR.glob("*.txt")}
    all_ids = email_ids | lead_ids | task_ids | note_ids

    for pattern in patterns:
        sources = pattern["source_ids"]
        assert len(sources) >= 3, f"pattern {pattern['name']} needs >=3 sources"
        missing = set(sources) - all_ids
        assert not missing, f"pattern {pattern['name']} references unknown ids: {missing}"
        assert pattern["minutes_per_occurrence"] > 0
        assert pattern["description"]


def test_ground_truth_declares_non_patterns() -> None:
    gt = json.loads((DATA_DIR / "GROUND_TRUTH.json").read_text(encoding="utf-8"))
    assert len(gt["non_patterns"]) >= 2, "expected at least 2 deliberate non-patterns"
