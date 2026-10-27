"""Phase 2 tests: ingestion pipeline (parsers + normalization)."""
from __future__ import annotations

from app.services.ingest import (
    parse_emails_csv,
    parse_leads_csv,
    parse_notes,
    parse_tasks_csv,
    strip_signature_and_quotes,
)


def test_emails_clean_row() -> None:
    csv_text = (
        "id,date,from,to,subject,body,labels\n"
        "E001,2025-01-10 16:20,maya@example.com,lead@example.com,"
        '"Weekly Pipeline Status","Hi all, here is the update.",sent\n'
    )
    artifacts = parse_emails_csv(csv_text)
    assert len(artifacts) == 1
    a = artifacts[0]
    assert a["kind"] == "email"
    assert a["source_ref"] == "E001"
    assert a["title"] == "Weekly Pipeline Status"
    assert a["timestamp"] is not None
    assert "maya@example.com" in a["text"]
    assert "lead@example.com" in a["text"]
    assert "Weekly Pipeline Status" in a["text"]


def test_emails_missing_date_tolerated() -> None:
    csv_text = (
        "id,date,from,to,subject,body,labels\n"
        "E002,,a@example.com,b@example.com,No date,Body here,inbox\n"
    )
    artifacts = parse_emails_csv(csv_text)
    assert len(artifacts) == 1
    assert artifacts[0]["timestamp"] is None


def test_malformed_csv_does_not_crash() -> None:
    csv_text = (
        "id,date,from,to,subject,body,labels\n"
        "E003,2025-01-09,a@example.com,b@example.com,'Unclosed quote,Body,inbox\n"
        "E004,not-a-date,c@example.com,d@example.com,Ok subject,Body2,inbox\n"
    )
    artifacts = parse_emails_csv(csv_text)
    # Should not raise; at least one row survives (the one after the broken line).
    assert len(artifacts) >= 1


def test_empty_file_returns_no_artifacts() -> None:
    assert parse_emails_csv("") == []
    assert parse_leads_csv("") == []
    assert parse_tasks_csv("") == []


def test_leads_messy_dates_and_missing_fields() -> None:
    csv_text = (
        "id,created,company,contact,email,source,status,notes\n"
        "L001,10-Jan-2025,Acme Corp,jane@example.com,,website,new,\n"
        "L002,01/09/2025,,,,referral,contacted,\n"
    )
    artifacts = parse_leads_csv(csv_text)
    assert len(artifacts) == 2
    assert artifacts[0]["timestamp"] is not None  # messy date still parsed
    assert "Acme Corp" in artifacts[0]["text"]
    # Second row has missing company/contact/email but must not crash.
    assert artifacts[1]["kind"] == "lead"


def test_notes_parsing_extracts_title_and_text() -> None:
    content = (
        "Weekly Pipeline Standup\n"
        "Monday, January 06, 2025 | 10:00 AM | Zoom\n"
        "Attendees: Maya, Dana\n\n"
        "Action items\n- Send status deck\n"
    )
    artifacts = parse_notes(content, filename="pipeline_standup.txt")
    assert len(artifacts) == 1
    a = artifacts[0]
    assert a["kind"] == "note"
    assert a["source_ref"] == "pipeline_standup"
    assert a["title"] == "Weekly Pipeline Standup"
    assert "Action items" in a["text"]


def test_tasks_parsing() -> None:
    csv_text = (
        "id,title,due,status,project,notes\n"
        "T001,Send weekly pipeline status,2025-01-10,done,Reporting,\n"
        "T002,Compile status email,01/17/2025,todo,Reporting,x\n"
    )
    artifacts = parse_tasks_csv(csv_text)
    assert len(artifacts) == 2
    assert artifacts[0]["kind"] == "task"
    assert "Send weekly pipeline status" in artifacts[0]["text"]


def test_strip_signature_and_quoted_chain() -> None:
    body = (
        "Here is the update you asked for.\n"
        "\n"
        "On Mon, Jan 6, 2025, someone else wrote:\n"
        "> Old quoted line one\n"
        "> Old quoted line two\n"
        "\n"
        "-- \n"
        "Maya Rao\nSales Operations\nmaya@example.com"
    )
    cleaned = strip_signature_and_quotes(body)
    assert "Here is the update" in cleaned
    assert "Old quoted line" not in cleaned
    assert "maya@example.com" not in cleaned
    assert "Sales Operations" not in cleaned
