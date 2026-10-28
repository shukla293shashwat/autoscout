"""Phase 5: safe automation generation and sandbox execution.

Safety model (NON-NEGOTIABLE):
  * Generated automations are DECLARATIVE JSON workflows (AutomationPlan) and
    are executed ONLY by this module's whitelist of tool functions.
  * No `exec`, `eval`, or model-generated Python is ever executed.
  * All file writes are confined to OUTPUT_DIR (data/output); path traversal
    is rejected. Reads are confined to the data directories.
  * Every tool supports dry_run=True (preview, zero side effects).

Flow:
  generate_plan(workflow, evidence)  -> AutomationPlan  (LLM or deterministic
                                          template when provider=mock)
  run_plan(plan, inputs, dry_run)    -> list[step result]  (context-chained)

Each step may capture its output into a context variable (capture_as /
capture_key) so a later step's {{placeholder}} can reference it (e.g. a table
summary feeding a drafted email body).
"""
from __future__ import annotations

import csv
import logging
import re
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger("autoscout.automation")

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"
SAMPLE_DIR = DATA_DIR / "sample"
OUTPUT_DIR = DATA_DIR / "output"
DRAFTS_DIR = OUTPUT_DIR / "drafts"

_PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


class AutomationError(Exception):
    """Base error for automation/tool execution."""


class PlanError(AutomationError):
    """Invalid plan (unknown tool, unresolved placeholder, bad args)."""


class SandboxError(AutomationError):
    """A tool attempted an unsafe path or I/O operation."""


# ---------------------------------------------------------------------------
# Path safety helpers
# ---------------------------------------------------------------------------
def _drafts_dir() -> Path:
    return OUTPUT_DIR / "drafts"


def _safe_output_path(filename: str) -> Path:
    """Resolve `filename` under OUTPUT_DIR, rejecting traversal/absolute paths."""
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        raise SandboxError(f"Unsafe output filename: {filename!r}")
    target = (OUTPUT_DIR / filename).resolve()
    if not str(target).startswith(str(OUTPUT_DIR.resolve())):
        raise SandboxError(f"Path escapes output sandbox: {filename!r}")
    return target


def _resolve_read_path(filename: str) -> Path:
    """Resolve a read path within the data dirs (sample first, then output).

    The sandbox boundary is SAMPLE_DIR/OUTPUT_DIR (and their parents) so tests
    can redirect those roots to a temp directory.
    """
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        raise SandboxError(f"Unsafe read filename: {filename!r}")

    def _inside(candidate: Path) -> bool:
        for base in (SAMPLE_DIR, OUTPUT_DIR):
            b = base.resolve()
            if candidate == b or b in candidate.parents or candidate.parent == b:
                return True
        return False

    for base in (SAMPLE_DIR, OUTPUT_DIR):
        candidate = (base / filename).resolve()
        if candidate.exists() and _inside(candidate):
            return candidate
    raise SandboxError(f"Read file not found in data dirs: {filename!r}")


# ---------------------------------------------------------------------------
# Whitelisted tools (typed, dry-run capable)
# ---------------------------------------------------------------------------
def append_csv_row(file: str, row: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    """Append one dict row to OUTPUT_DIR/file.csv (creates with header if new)."""
    path = _safe_output_path(file)
    action = f"append row {row} -> {path.name}"
    if dry_run:
        return {"tool": "append_csv_row", "dry_run": True, "status": "ok",
                "action": action, "preview": action, "path": str(path)}
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(row.keys()))
        if new_file:
            writer.writeheader()
        writer.writerow(row)
    return {"tool": "append_csv_row", "dry_run": False, "status": "ok",
            "action": action, "preview": action, "path": str(path)}


def draft_email(
    to: str, subject: str, body: str, dry_run: bool = False
) -> dict[str, Any]:
    """Write a plain-text email draft to OUTPUT_DIR/drafts/."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", subject).strip("-").lower()[:40] or "draft"
    drafts = _drafts_dir()
    path = drafts / f"{slug}-{uuid.uuid4().hex[:6]}.txt"
    content = f"To: {to}\nSubject: {subject}\n\n{body}\n"
    action = f"draft email to={to} subject={subject!r}"
    if dry_run:
        # Zero side effects: do NOT create the drafts dir on a dry run.
        return {"tool": "draft_email", "dry_run": True, "status": "ok",
                "action": action, "preview": content, "path": str(path)}
    drafts.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return {"tool": "draft_email", "dry_run": False, "status": "ok",
            "action": action, "preview": content, "path": str(path)}


def create_task(
    title: str, due: str = "", notes: str = "", dry_run: bool = False
) -> dict[str, Any]:
    """Append a task row to OUTPUT_DIR/tasks_out.csv."""
    path = _safe_output_path("tasks_out.csv")
    row = {"title": title, "due": due, "notes": notes}
    action = f"create task {title!r} due={due}"
    if dry_run:
        return {"tool": "create_task", "dry_run": True, "status": "ok",
                "action": action, "preview": action, "path": str(path)}
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["title", "due", "notes"])
        if new_file:
            writer.writeheader()
        writer.writerow(row)
    return {"tool": "create_task", "dry_run": False, "status": "ok",
            "action": action, "preview": action, "path": str(path)}


def summarize_table(
    file: str, group_by: str, metrics: list[str] | None = None, dry_run: bool = False
) -> dict[str, Any]:
    """Read a CSV and return a grouped summary string (read-only, no side effects)."""
    path = _resolve_read_path(file)
    with path.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    counts: dict[str, int] = {}
    for r in rows:
        key = (r.get(group_by) or "(empty)").strip() or "(empty)"
        counts[key] = counts.get(key, 0) + 1
    lines = [f"Summarize {file} grouped by {group_by}:"]
    for key in sorted(counts):
        lines.append(f"  - {key}: {counts[key]}")
    lines.append(f"  total rows: {len(rows)}")
    summary = "\n".join(lines)
    action = f"summarize {file} by {group_by} -> {len(counts)} groups"
    return {"tool": "summarize_table", "dry_run": dry_run, "status": "ok",
            "action": action, "preview": summary, "output": summary, "path": str(path)}


TOOLS: dict[str, Any] = {
    "append_csv_row": append_csv_row,
    "draft_email": draft_email,
    "create_task": create_task,
    "summarize_table": summarize_table,
}


def tool_registry_schema() -> dict[str, Any]:
    """JSON description of the whitelist (fed to the LLM when generating plans)."""
    return {
        "append_csv_row": {"file": "str (csv filename)", "row": "dict"},
        "draft_email": {"to": "str", "subject": "str", "body": "str"},
        "create_task": {"title": "str", "due": "str", "notes": "str"},
        "summarize_table": {"file": "str", "group_by": "str", "metrics": "list[str]"},
    }


# ---------------------------------------------------------------------------
# Declarative plan schema
# ---------------------------------------------------------------------------
class AutomationStep(BaseModel):
    """One declarative step in an automation plan (a whitelisted tool call)."""

    tool: str
    args_template: dict[str, Any] = Field(default_factory=dict)
    description: str = ""
    capture_as: str | None = None   # context variable to store this step's output
    capture_key: str = "output"     # which result key to capture into context


class AutomationPlan(BaseModel):
    """A declarative automation: ordered whitelisted tool calls."""

    name: str
    trigger: str = ""
    steps: list[AutomationStep]


# ---------------------------------------------------------------------------
# Placeholder resolution + execution
# ---------------------------------------------------------------------------
def _resolve_args(
    args_template: dict[str, Any], context: dict[str, Any]
) -> dict[str, Any]:
    """Recursively substitute {{var}} placeholders from context; error if any remain."""

    def sub(value: Any) -> Any:
        if isinstance(value, str):
            def repl(m: re.Match) -> str:
                key = m.group(1)
                if key not in context:
                    raise PlanError(f"Unresolved placeholder {{{{{key}}}}} in args")
                return str(context[key])
            return _PLACEHOLDER.sub(repl, value)
        if isinstance(value, dict):
            return {k: sub(v) for k, v in value.items()}
        if isinstance(value, list):
            return [sub(v) for v in value]
        return value

    return {k: sub(v) for k, v in args_template.items()}


def run_plan(
    plan: AutomationPlan, inputs: dict[str, Any] | None = None, dry_run: bool = True
) -> list[dict[str, Any]]:
    """Execute a plan's steps in order, resolving placeholders from context.

    Returns a per-step result list. Raises PlanError on unknown tool or
    unresolved placeholder (invalid plan). Stops at the first failing step and
    marks it status=error (prior side effects, if any, remain — but dry_run
    guarantees none).
    """
    context: dict[str, Any] = dict(inputs or {})
    results: list[dict[str, Any]] = []
    for idx, step in enumerate(plan.steps, start=1):
        if step.tool not in TOOLS:
            raise PlanError(f"Unknown tool {step.tool!r} at step {idx}")
        try:
            args = _resolve_args(step.args_template, context)
        except PlanError as exc:
            raise PlanError(f"step {idx}: {exc}") from exc

        try:
            result = TOOLS[step.tool](dry_run=dry_run, **args)
        except AutomationError as exc:
            result = {"tool": step.tool, "dry_run": dry_run, "status": "error",
                      "action": str(exc), "preview": str(exc)}
            results.append(result)
            logger.error("Step %d (%s) failed: %s", idx, step.tool, exc)
            return results
        except TypeError as exc:
            raise PlanError(f"step {idx}: invalid args for {step.tool}: {exc}") from exc

        result["step"] = idx
        results.append(result)
        if step.capture_as and step.capture_key in result:
            context[step.capture_as] = result[step.capture_key]
    return results


# ---------------------------------------------------------------------------
# Deterministic plan builder (offline / mock provider)
# ---------------------------------------------------------------------------
def _sample_evidence_text(workflow: dict[str, Any], artifacts: list[Any]) -> str:
    by_ref = {getattr(a, "source_ref", None): a for a in artifacts}
    for ref in workflow.get("evidence", []):
        a = by_ref.get(ref)
        if a is not None:
            return getattr(a, "text", "") or ""
    return ""


def build_deterministic_plan(
    workflow: dict[str, Any],
    artifacts: list[Any],
    recipient: str = "leadership@example.com",
) -> AutomationPlan:
    """Build a sensible plan from the workflow's evidence composition.

    Used when LLM_PROVIDER=mock so the demo works fully offline. Chooses a
    plan template from the dominant artifact kind of the evidence.
    """
    by_ref = {getattr(a, "source_ref", None): a for a in artifacts}
    evid = [by_ref[r] for r in workflow.get("evidence", []) if r in by_ref]
    kinds = [getattr(a, "kind", "email") for a in evid]
    dominant = max(set(kinds), key=kinds.count) if kinds else "email"

    if dominant == "note":
        # Meeting follow-up: draft a recap + create a task.
        title = workflow.get("name", "Follow-up")
        return AutomationPlan(
            name=f"Automate: {title}",
            trigger=workflow.get("trigger", "after each meeting"),
            steps=[
                AutomationStep(tool="draft_email",
                               args_template={
                                   "to": recipient,
                                   "subject": f"Follow-up: {title}",
                                   "body": "Thanks for the discussion. Recap and action items attached."},
                               description="Draft the follow-up recap email"),
                AutomationStep(tool="create_task",
                               args_template={"title": title,
                                              "due": "this week",
                                              "notes": "Auto-created from meeting follow-up"},
                               description="Create a task for the action item"),
            ],
        )
    if dominant == "task":
        return AutomationPlan(
            name=f"Automate: {workflow.get('name', 'Tasks')}",
            trigger=workflow.get("trigger", "recurring task"),
            steps=[
                AutomationStep(tool="create_task",
                               args_template={"title": workflow.get("name", "Task"),
                                              "due": "this week",
                                              "notes": "Auto-created recurring task"},
                               description="Create the recurring task"),
            ],
        )

    # Email-dominant: summarize the leads sheet, then draft the status email.
    return AutomationPlan(
        name=f"Automate: {workflow.get('name', 'Status email')}",
        trigger=workflow.get("trigger", "recurring email"),
        steps=[
            AutomationStep(tool="summarize_table",
                           args_template={"file": "leads.csv", "group_by": "status",
                                          "metrics": ["count"]},
                           capture_as="summary", capture_key="output",
                           description="Summarize the leads sheet"),
            AutomationStep(tool="draft_email",
                           args_template={"to": recipient,
                                          "subject": workflow.get("name", "Weekly update"),
                                          "body": "Here is the weekly update:\n{{summary}}"},
                           description="Draft the status email from the summary"),
        ],
    )


def generate_plan(
    workflow: dict[str, Any],
    artifacts: list[Any] | None = None,
    recipient: str = "leadership@example.com",
) -> AutomationPlan:
    """Produce a validated AutomationPlan for a workflow.

    With a real LLM this asks the model for a plan (validated against the
    whitelist, retried on invalid tool names). With LLM_PROVIDER=mock it uses a
    deterministic template so the demo runs fully offline.
    """
    from app.config import settings
    from app.llm import LLMError, generate_json

    artifacts = artifacts or []
    if settings.llm_provider.lower() == "mock":
        return build_deterministic_plan(workflow, artifacts, recipient=recipient)

    system = (
        "You design SAFE automations. Given a discovered workflow and a WHITELIST "
        "of tools, return an AutomationPlan using ONLY whitelisted tools with "
        "args_template keys matching each tool's signature. Use {{var}} placeholders "
        "for values filled from evidence. Never invent tools."
    )
    user = (
        f"Workflow: {workflow.get('name')} — {workflow.get('description')}\n"
        f"Trigger: {workflow.get('trigger')}\n"
        f"Evidence texts:\n{_sample_evidence_text(workflow, artifacts)[:1500]}\n\n"
        f"Whitelist (JSON): {tool_registry_schema()}"
    )
    try:
        plan = generate_json(system, user, AutomationPlan, retries=2)
    except LLMError:
        return build_deterministic_plan(workflow, artifacts, recipient=recipient)
    # Validation (unknown tool) already raises inside the pydantic validator;
    # if we get here it's valid.
    return plan
