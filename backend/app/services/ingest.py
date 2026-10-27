"""Phase 2: ingestion and normalization.

Parsers for emails.csv, leads.csv, tasks.csv, and .txt meeting notes.
Every row is normalized into an Artifact dict with a clean ``text`` field
optimized for semantic analysis. Bad dates and missing columns are
tolerated without crashing; skipped rows are logged.
"""
from __future__ import annotations

import csv
import io
import logging
import re
from datetime import datetime
from typing import Any

logger = logging.getLogger("autoscout.ingest")

Artifact = dict[str, Any]

# ---------------------------------------------------------------------------
# Date parsing: tolerant, returns None instead of raising.
# ---------------------------------------------------------------------------
_DATE_FORMATS = [
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%m/%d/%Y %I:%M %p",
    "%m/%d/%Y",
    "%d-%b-%Y %H:%M",
    "%d-%b-%Y",
    "%b %d, %Y",
    "%d %b %Y %H:%M",
    "%d %b %Y",
]


def parse_date(value: str | None) -> datetime | None:
    """Parse a messy date string; return None when unparseable."""
    if not value or not value.strip():
        return None
    value = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    # Last resort: try ISO with a T separator.
    try:
        return datetime.fromisoformat(value.replace("Z", ""))
    except ValueError:
        logger.debug("Unparseable date %r; storing None", value)
        return None


# ---------------------------------------------------------------------------
# Email cleanup heuristic
# ---------------------------------------------------------------------------
_SIGNATURE_MARKERS = [
    re.compile(r"^--\s*$", re.MULTILINE),
    re.compile(r"^--\s*$", re.MULTILINE),
    re.compile(r"^_{5,}\s*$", re.MULTILINE),
    re.compile(r"^\s*Best regards,?\s*$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*Sent from my", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*Get Outlook", re.IGNORECASE | re.MULTILINE),
]
_QUOTE_HEADER = re.compile(
    r"^\s*On .+wrote:\s*$|^\s*On .+said:\s*$|^\s*-{2,}\s*Original Message\s*-{2,}\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def strip_signature_and_quotes(body: str) -> str:
    """Remove reply chains and signature blocks from an email body."""
    if not body:
        return ""
    text = body

    # Cut everything from the first quote header (e.g. "On Mon, Jan 6, X wrote:").
    m = _QUOTE_HEADER.search(text)
    if m:
        text = text[: m.start()]

    # Cut a signature: from the first signature marker onward.
    cut = len(text)
    for pat in _SIGNATURE_MARKERS:
        m = pat.search(text)
        if m:
            cut = min(cut, m.start())
    text = text[:cut]

    # Drop any remaining quoted lines starting with ">".
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith(">")]
    return "\n".join(lines).strip()


def _normalize_header(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


# ---------------------------------------------------------------------------
# CSV parsing helpers
# ---------------------------------------------------------------------------
def _read_dicts(csv_text: str) -> list[dict[str, str]]:
    """Read CSV text into a list of dicts with normalized headers.

    Returns [] for empty input. Malformed rows are skipped (the csv module
    tolerates unclosed quotes by merging rows; we drop rows that lack any
    usable id).
    """
    if not csv_text or not csv_text.strip():
        return []
    reader = csv.DictReader(io.StringIO(csv_text))
    rows: list[dict[str, str]] = []
    for i, raw in enumerate(reader):
        if raw is None:
            continue
        row: dict[str, str] = {}
        for k, v in raw.items():
            if k is None:
                continue
            row[_normalize_header(k)] = (v or "").strip() if isinstance(v, str) else ""
        if not any(row.values()):
            continue  # blank line
        rows.append(row)
    return rows


def _get(row: dict[str, str], *keys: str) -> str:
    for k in keys:
        if k in row and row[k]:
            return row[k]
    return ""


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------
def parse_emails_csv(csv_text: str) -> list[Artifact]:
    """Parse an emails export into Artifact dicts."""
    artifacts: list[Artifact] = []
    for row in _read_dicts(csv_text):
        eid = _get(row, "id", "message_id", "messageid")
        subject = _get(row, "subject", "title")
        frm = _get(row, "from", "sender")
        to = _get(row, "to", "recipient")
        date_raw = _get(row, "date", "timestamp", "sent_at")
        body = _get(row, "body", "text", "content")
        labels = _get(row, "labels", "label", "category")

        if not eid:
            eid = f"email-{len(artifacts) + 1}"

        cleaned_body = strip_signature_and_quotes(body)
        ts = parse_date(date_raw)

        text = (
            f"Email from {frm or 'unknown'} to {to or 'unknown'}"
            + (f" on {ts.strftime('%Y-%m-%d')}" if ts else "")
            + f". Subject: {subject or '(no subject)'}. Body: {cleaned_body}"
        )

        artifacts.append({
            "kind": "email",
            "source_ref": eid,
            "timestamp": ts,
            "title": subject or "(no subject)",
            "text": text,
            "raw_json": {
                "from": frm,
                "to": to,
                "subject": subject,
                "labels": labels,
                "body": cleaned_body,
            },
        })
    return artifacts


def parse_leads_csv(csv_text: str) -> list[Artifact]:
    """Parse a messy leads spreadsheet into Artifact dicts."""
    artifacts: list[Artifact] = []
    for row in _read_dicts(csv_text):
        lid = _get(row, "id", "lead_id")
        company = _get(row, "company", "account", "account_name")
        contact = _get(row, "contact", "name", "full_name")
        email = _get(row, "email", "email_address")
        source = _get(row, "source", "channel")
        status = _get(row, "status", "stage")
        created_raw = _get(row, "created", "created_at", "date", "added")

        if not lid:
            lid = f"lead-{len(artifacts) + 1}"

        ts = parse_date(created_raw)
        parts = []
        if company:
            parts.append(f"Company: {company}.")
        if contact:
            parts.append(f"Contact: {contact}.")
        if email:
            parts.append(f"Email: {email}.")
        if source:
            parts.append(f"Source: {source}.")
        if status:
            parts.append(f"Status: {status}.")
        if not parts:
            parts.append("Lead with no identifying fields.")
        text = f"Lead record. {' '.join(parts)}"

        artifacts.append({
            "kind": "lead",
            "source_ref": lid,
            "timestamp": ts,
            "title": company or contact or lid,
            "text": text,
            "raw_json": dict(row),
        })
    return artifacts


def parse_tasks_csv(csv_text: str) -> list[Artifact]:
    """Parse a to-do export into Artifact dicts."""
    artifacts: list[Artifact] = []
    for row in _read_dicts(csv_text):
        tid = _get(row, "id", "task_id")
        title = _get(row, "title", "name", "summary")
        due_raw = _get(row, "due", "due_date", "deadline")
        status = _get(row, "status")
        project = _get(row, "project", "list")
        notes = _get(row, "notes", "description")

        if not tid:
            tid = f"task-{len(artifacts) + 1}"

        ts = parse_date(due_raw)
        label = title or "(untitled)"
        parts = [f"Task: {label}."]
        if project:
            parts.append(f"Project: {project}.")
        if status:
            parts.append(f"Status: {status}.")
        if ts:
            parts.append(f"Due: {ts.strftime('%Y-%m-%d')}.")
        if notes:
            parts.append(f"Notes: {notes}.")
        text = " ".join(parts)

        artifacts.append({
            "kind": "task",
            "source_ref": tid,
            "timestamp": ts,
            "title": title or "(untitled)",
            "text": text,
            "raw_json": dict(row),
        })
    return artifacts


def parse_notes(content: str, filename: str = "note.txt") -> list[Artifact]:
    """Parse a .txt meeting note into a single Artifact dict."""
    if not content or not content.strip():
        return []
    stem = filename.rsplit(".", 1)[0]
    lines = content.splitlines()
    title = ""
    for ln in lines:
        if ln.strip():
            title = ln.strip()
            break
    if not title:
        title = stem
    # Prefer a parseable date line if present (second line often has the date).
    ts: datetime | None = None
    for ln in lines[1:4]:
        ts = parse_date(ln.split("|")[0].strip())
        if ts:
            break

    text = f"Meeting note: {title}.\n{content.strip()}"
    return [{
        "kind": "note",
        "source_ref": stem,
        "timestamp": ts,
        "title": title,
        "text": text,
        "raw_json": {"filename": filename, "content": content},
    }]


# ---------------------------------------------------------------------------
# Dispatch by filename
# ---------------------------------------------------------------------------
def parse_file(filename: str, content: str) -> list[Artifact]:
    """Route a file to the right parser based on its filename."""
    name = filename.lower()
    if name.endswith(".txt"):
        return parse_notes(content, filename=filename)
    if "email" in name and name.endswith(".csv"):
        return parse_emails_csv(content)
    if "lead" in name and name.endswith(".csv"):
        return parse_leads_csv(content)
    if "task" in name and name.endswith(".csv"):
        return parse_tasks_csv(content)
    if name.endswith(".csv"):
        # Fallback: try emails then leads then tasks.
        for parser in (parse_emails_csv, parse_leads_csv, parse_tasks_csv):
            result = parser(content)
            if result:
                return result
        return []
    logger.warning("Unsupported file type: %s", filename)
    return []
