"""Phase 3 tests: pattern discovery engine.

These tests exercise the pure helper functions (embedding, filtering,
evidence validation) plus the end-to-end discover pipeline on the committed
sample dataset (using the deterministic mock LLM provider).

Accuracy is measured the way the product cares about it (see
scripts/eval_discovery.py): for each ground-truth pattern we require that the
discovered workflows' evidence (union) covers >= 60% of the pattern's source
ids, and we require overall precision >= 0.5 (majority of discovered evidence
is genuine ground-truth work).
"""
from __future__ import annotations

import json
from pathlib import Path

from app.services.discovery import (
    _filter_clusters,
    _validate_evidence,
    discover_workflows,
    embed_texts,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
SAMPLE_DIR = REPO_ROOT / "data" / "sample"

COVERAGE_THRESHOLD = 0.6
PRECISION_THRESHOLD = 0.5


def _load_ground_truth() -> dict:
    return json.loads((SAMPLE_DIR / "GROUND_TRUTH.json").read_text(encoding="utf-8"))


def _ingest_sample() -> int:
    """Ingest the committed sample into a fresh in-memory upload; return id."""
    from app.db import SessionLocal, init_db
    from app.models import Artifact, Upload
    from app.services.ingest import parse_file

    init_db()
    db = SessionLocal()
    upload = Upload(filename="sample", is_sample=1)
    db.add(upload)
    db.flush()
    for path in sorted(SAMPLE_DIR.rglob("*")):
        if path.is_dir() or path.name.startswith("."):
            continue
        if path.suffix.lower() not in {".csv", ".txt"}:
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        for a in parse_file(path.name, content):
            db.add(Artifact(
                upload_id=upload.id,
                kind=a["kind"],
                source_ref=a.get("source_ref", ""),
                timestamp=a.get("timestamp"),
                title=a.get("title", ""),
                text=a.get("text", ""),
                raw_json=json.dumps(a.get("raw_json", {}), default=str),
            ))
    db.commit()
    uid = upload.id
    db.close()
    return uid


def test_embed_texts_shape() -> None:
    vectors = embed_texts(["hello world", "foo bar", "baz qux"])
    assert len(vectors) == 3
    assert len(vectors[0]) == 384  # all-MiniLM-L6-v2 output dim


def test_filter_clusters_keeps_recurring_drops_tiny() -> None:
    clusters = [
        [(0, "2025-01-06"), (1, "2025-01-08"), (2, "2025-01-10"), (3, "2025-01-10"), (4, "2025-01-09")],
        [(5, "2025-01-06"), (6, "2025-01-07")],
        [(7, "2025-01-06"), (8, "2025-01-06"), (9, "2025-01-06"), (10, "2025-01-06")],
    ]
    kept = _filter_clusters(clusters, min_size=3, min_days=2)
    assert len(kept) == 1
    assert [i for i, _ in kept[0]] == [0, 1, 2, 3, 4]


def test_validate_evidence_drops_hallucinated_ids() -> None:
    valid = ["E001", "E002", "E003"]
    claimed = ["E001", "E999", "E003"]
    assert _validate_evidence(claimed, valid) == ["E001", "E003"]


def test_discover_finds_all_three_patterns() -> None:
    gt = _load_ground_truth()
    # For coverage, replies are the confirmation half of the inbound workflow;
    # matching the inbound requests (first 12) is sufficient evidence.
    expected = {p["id"]: set(p["source_ids"]) for p in gt["patterns"]}
    for p in gt["patterns"]:
        if p["id"] == "B":
            expected["B"] = set(p["source_ids"][:12])

    upload_id = _ingest_sample()
    from app.db import SessionLocal
    db = SessionLocal()
    try:
        workflows = discover_workflows(db, upload_id)
        assert workflows, "discovery returned no workflows"
        discovered_union = set()
        for wf in workflows:
            discovered_union.update(wf["evidence"])

        covered = {}
        for pid, sources in expected.items():
            cov = len(discovered_union & sources) / len(sources)
            covered[pid] = cov

        missed = [pid for pid, cov in covered.items() if cov < COVERAGE_THRESHOLD]
        assert not missed, (
            f"patterns below {COVERAGE_THRESHOLD} coverage: { {p: round(covered[p],2) for p in missed} }"
        )
        # Precision: share of discovered evidence that is real ground-truth work.
        all_gt = set().union(*expected.values())
        precision = len(discovered_union & all_gt) / len(discovered_union)
        assert precision >= PRECISION_THRESHOLD, f"precision {precision:.2f} < {PRECISION_THRESHOLD}"
    finally:
        db.close()
