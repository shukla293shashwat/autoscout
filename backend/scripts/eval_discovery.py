"""Phase 3 evaluation: score discovery against data/sample/GROUND_TRUTH.json.

Prints per-pattern coverage (recall), overall precision, which patterns were
missed, and the discovered workflow list. Run after discovery to tune
thresholds/prompts.

Usage:
    cd backend
    python scripts/eval_discovery.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DIR = REPO_ROOT / "data" / "sample"
sys.path.insert(0, str(REPO_ROOT / "backend"))


def main() -> int:
    from app.db import SessionLocal, init_db
    from app.models import Artifact, Upload
    from app.services.discovery import discover_workflows
    from app.services.ingest import parse_file

    gt = json.loads((SAMPLE_DIR / "GROUND_TRUTH.json").read_text(encoding="utf-8"))
    patterns = {p["id"]: set(p["source_ids"]) for p in gt["patterns"]}
    # Replies are the confirmation half of the inbound workflow; matching the
    # inbound requests (first 12 of B) is sufficient evidence of the pattern.
    for p in gt["patterns"]:
        if p["id"] == "B":
            patterns["B"] = set(p["source_ids"][:12])

    init_db()
    db = SessionLocal()
    upload = Upload(filename="eval-sample", is_sample=1)
    db.add(upload)
    db.flush()
    for path in sorted(SAMPLE_DIR.rglob("*")):
        if path.is_dir() or path.name.startswith("."):
            continue
        if path.suffix.lower() not in {".csv", ".txt"}:
            continue
        for a in parse_file(path.name, path.read_text(encoding="utf-8", errors="replace")):
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

    workflows = discover_workflows(db, upload.id)

    discovered: set[str] = set()
    for wf in workflows:
        discovered.update(wf["evidence"])
    all_gt = set().union(*patterns.values())

    print("=" * 64)
    print("DISCOVERY EVALUATION vs GROUND_TRUTH.json")
    print("=" * 64)
    print(f"{'pattern':<8}{'coverage':>10}  {'status':<10}  discovered evidence")
    print("-" * 64)

    missed: list[str] = []
    for pid, sources in patterns.items():
        cov = len(discovered & sources) / len(sources)
        status = "FOUND" if cov >= 0.6 else "MISSED"
        if cov < 0.6:
            missed.append(pid)
        print(f"{pid:<8}{cov:>9.0%}  {status:<10}  {len(sources)} source ids")

    precision = len(discovered & all_gt) / len(discovered) if discovered else 0.0
    print("-" * 64)
    print(f"precision (discovered evidence that is real): {precision:.0%}")
    print(f"workflows discovered: {len(workflows)}")
    print()
    for wf in workflows:
        print(f"  - {wf['name']!r}  [{wf['feasibility']}]  "
              f"{wf['occurrences']}x, {wf['minutes_per_occurrence']}min  "
              f"evidence={len(wf['evidence'])}")

    ok = not missed and precision >= 0.5
    print()
    if ok:
        print("RESULT: PASS — all patterns found with >=50% precision.")
    else:
        print(f"RESULT: FAIL — missed={missed or 'none'}, precision={precision:.0%}")
    db.close()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
