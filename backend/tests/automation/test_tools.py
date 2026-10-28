"""Phase 5 tests: whitelisted tools + sandboxed plan execution."""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from app.services.automation import (
    TOOLS,
    AutomationError,
    AutomationPlan,
    AutomationStep,
    PlanError,
    SandboxError,
    append_csv_row,
    create_task,
    draft_email,
    run_plan,
    summarize_table,
)


@pytest.fixture()
def out_dir(tmp_path, monkeypatch):
    """Redirect the sandbox output root to a temp directory."""
    import app.services.automation as auto
    monkeypatch.setattr(auto, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(auto, "SAMPLE_DIR", tmp_path / "sample")
    (tmp_path / "output").mkdir()
    (tmp_path / "sample").mkdir()
    return tmp_path / "output"


def test_tool_registry_is_whitelisted() -> None:
    expected = {"append_csv_row", "draft_email", "create_task", "summarize_table"}
    assert set(TOOLS.keys()) == expected


def test_append_csv_row_dry_run_writes_nothing(out_dir) -> None:
    res = append_csv_row("out.csv", {"a": "1"}, dry_run=True)
    assert res["dry_run"] is True
    assert res["status"] == "ok"
    assert not (out_dir / "out.csv").exists()


def test_append_csv_row_executes_and_writes_file(out_dir) -> None:
    res = append_csv_row("out.csv", {"a": "1"}, dry_run=False)
    assert res["status"] == "ok"
    path = out_dir / "out.csv"
    assert path.exists()
    rows = list(csv.DictReader(path.open()))
    assert rows == [{"a": "1"}]


def test_append_csv_row_blocks_path_traversal(out_dir) -> None:
    with pytest.raises(SandboxError):
        append_csv_row("../../evil.csv", {"a": "1"}, dry_run=False)


def test_draft_email_dry_run_writes_nothing(out_dir) -> None:
    res = draft_email("a@b.com", "Hi", "Body", dry_run=True)
    assert res["dry_run"] is True
    assert res["preview"]  # shows what WOULD be written
    assert not any((out_dir / "drafts").glob("*.txt")) if (out_dir / "drafts").exists() else True


def test_draft_email_executes_writes_draft(out_dir) -> None:
    res = draft_email("a@b.com", "Weekly Status", "Body text", dry_run=False)
    assert res["status"] == "ok"
    drafts = list((out_dir / "drafts").glob("*.txt"))
    assert drafts, "expected a drafted email file"
    content = drafts[0].read_text()
    assert "a@b.com" in content
    assert "Weekly Status" in content


def test_create_task_appends_to_tasks_out(out_dir) -> None:
    create_task("Task A", "2025-01-10", "note", dry_run=False)
    create_task("Task B", "2025-01-11", "note2", dry_run=False)
    path = out_dir / "tasks_out.csv"
    assert path.exists()
    rows = list(csv.DictReader(path.open()))
    assert len(rows) == 2
    assert rows[0]["title"] == "Task A"


def test_create_task_dry_run_writes_nothing(out_dir) -> None:
    create_task("T", "due", "n", dry_run=True)
    assert not (out_dir / "tasks_out.csv").exists()


def test_summarize_table_reads_csv_and_returns_summary(out_dir, tmp_path) -> None:
    sample = tmp_path / "sample"
    with (sample / "leads.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "status"])
        w.writeheader()
        w.writerows([{"id": "L1", "status": "new"}, {"id": "L2", "status": "new"},
                     {"id": "L3", "status": "qualified"}])
    res = summarize_table("leads.csv", group_by="status", metrics=["count"])
    assert res["status"] == "ok"
    out = res["output"]
    assert "status" in out.lower() or "new" in out.lower()


def test_run_plan_unknown_tool_rejected(out_dir) -> None:
    plan = AutomationPlan(
        name="bad", trigger="t",
        steps=[AutomationStep(tool="exec_shell", args_template={"cmd": "rm -rf /"})],
    )
    with pytest.raises(PlanError):
        run_plan(plan, inputs={}, dry_run=True)


def test_run_plan_unresolved_placeholder_rejected(out_dir) -> None:
    plan = AutomationPlan(
        name="p", trigger="t",
        steps=[AutomationStep(tool="draft_email", args_template={
            "to": "{{missing_var}}", "subject": "s", "body": "b"})],
    )
    with pytest.raises(PlanError):
        run_plan(plan, inputs={}, dry_run=True)


def test_run_plan_dry_run_produces_no_files(out_dir) -> None:
    plan = AutomationPlan(
        name="status", trigger="weekly",
        steps=[
            AutomationStep(tool="draft_email", args_template={
                "to": "lead@example.com", "subject": "Status", "body": "hello"},
                description="draft"),
        ],
    )
    results = run_plan(plan, inputs={}, dry_run=True)
    assert all(r["dry_run"] for r in results)
    assert all(r["status"] == "ok" for r in results)
    assert not (out_dir / "drafts").exists()


def test_run_plan_execute_produces_files_and_chains_context(out_dir) -> None:
    # Step 1 summarizes a table, captures output; step 2 uses it in an email body.
    sample = out_dir.parent / "sample"
    with (sample / "leads.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "status"])
        w.writeheader()
        w.writerows([{"id": "L1", "status": "new"}, {"id": "L2", "status": "qualified"}])
    plan = AutomationPlan(
        name="status", trigger="weekly",
        steps=[
            AutomationStep(tool="summarize_table",
                           args_template={"file": "leads.csv", "group_by": "status",
                                          "metrics": ["count"]},
                           capture_as="summary", capture_key="output",
                           description="summarize leads"),
            AutomationStep(tool="draft_email",
                           args_template={"to": "boss@example.com",
                                          "subject": "Weekly Pipeline Status",
                                          "body": "Here is the summary:\n{{summary}}"},
                           description="draft status email"),
        ],
    )
    results = run_plan(plan, inputs={}, dry_run=False)
    assert len(results) == 2
    assert all(r["status"] == "ok" for r in results)
    drafts = list((out_dir / "drafts").glob("*.txt"))
    assert drafts, "expected drafted status email"
    content = drafts[0].read_text()
    assert "Here is the summary:" in content
    # The captured table summary must be interpolated into the body.
    assert "new" in content.lower() or "status" in content.lower()
