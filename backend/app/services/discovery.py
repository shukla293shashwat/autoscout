"""Phase 3: pattern discovery engine.

Pipeline (see scripts/eval_discovery.py for the measured accuracy):
  1. Normalize each artifact to a *discriminating* text for clustering
     (the email body / note content / task text — NOT the shared
     "Email from X to Y" boilerplate that otherwise dilutes the signal).
  2. Cluster with a semantic+lexical union-find: two items join only if their
     cosine similarity >= PHI **and** their word-level Jaccard >= TAU. This
     groups near-templated repeats while the lexical gate stops loosely-related
     items from chaining across days.
  3. Direction gate: a workflow requires the user to be the *actor*. Authored
     (sent) emails, notes, and tasks can form workflows. Received inbox emails
     only count when they are the inbound half of a thread the user replied to
     (subject-linked "Re:" reply). Pure received noise (calendar invites,
     newsletters, social) is never linked and is therefore dropped.
  4. Recurrence filter: keep clusters spanning >= MIN_DAYS distinct days.
  5. For each surviving cluster, ask the LLM for a WorkflowCandidate
     (Pydantic-validated) using 5 representative items + cluster stats.
  6. Validate evidence ids against the cluster (drop hallucinated ids); store
     the full validated cluster as evidence for ROI/scoring.
  7. Deterministic fallback if the LLM fails (default name + time estimate).
  8. Persist Workflow rows with status=discovered.
"""
from __future__ import annotations

import json
import logging
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.llm import LLMError, generate_json
from app.models import Artifact, Workflow

logger = logging.getLogger("autoscout.discovery")

# ---------------------------------------------------------------------------
# Tunable clustering parameters (validated by scripts/eval_discovery.py)
# ---------------------------------------------------------------------------
PHI = 0.50        # minimum cosine similarity (embeddings) for two items to join
TAU = 0.20        # minimum word-level Jaccard for two items to join
REPLY_PHI = 0.45  # looser gate for reply templates (near-verbatim, WANT to merge)
REPLY_TAU = 0.10  # minimum word-level Jaccard for reply templates
MIN_CLUSTER = 3   # minimum items to form a candidate
MIN_DAYS = 2      # minimum distinct calendar days a cluster must span

# ---------------------------------------------------------------------------
# Embeddings (cached on disk under backend/.embed_cache/)
# ---------------------------------------------------------------------------
_EMBED_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / ".embed_cache"
_MODEL_NAME = "all-MiniLM-L6-v2"
_model: Any = None  # lazily loaded SentenceTransformer


def _get_model() -> Any:
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts with all-MiniLM-L6-v2, memoizing each string to disk."""
    model = _get_model()
    vectors: list[list[float]] = []
    to_encode: list[tuple[int, str]] = []
    for i, text in enumerate(texts):
        key = _cache_path(text)
        if key.exists():
            try:
                vectors.append(json.loads(key.read_text(encoding="utf-8")))
                continue
            except (OSError, json.JSONDecodeError):
                pass
        vectors.append([])  # placeholder
        to_encode.append((i, text))

    if to_encode:
        encoded = model.encode([t for _, t in to_encode], normalize_embeddings=True)
        for (i, _), vec in zip(to_encode, encoded):
            vec_list = [float(x) for x in vec]
            vectors[i] = vec_list
            _write_cache(texts[i], vec_list)
    return vectors


def _cache_path(text: str) -> Path:
    import hashlib
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return _EMBED_CACHE_DIR / f"{digest}.json"


def _write_cache(text: str, vec: list[float]) -> None:
    try:
        _EMBED_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(text).write_text(json.dumps(vec), encoding="utf-8")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Clustering text helpers
# ---------------------------------------------------------------------------
def _subject(a: Artifact) -> str:
    try:
        raw = json.loads(a.raw_json or "{}")
    except json.JSONDecodeError:
        raw = {}
    return (raw.get("subject") or a.title or "").strip()


def _email_body(a: Artifact) -> str:
    try:
        raw = json.loads(a.raw_json or "{}")
    except json.JSONDecodeError:
        raw = {}
    return (raw.get("body") or "").strip()


def _cluster_text(a: Artifact) -> str:
    """Text used for clustering: body for emails, full text for notes/tasks."""
    if a.kind == "email":
        return _email_body(a) or a.text
    return a.text


def _norm_subject(s: str) -> str:
    """Normalize a subject for thread matching: strip Re:/Fwd:, collapse case/whitespace."""
    s = re.sub(r"^(re|fw|fwd)\s*:?\s*", "", s.strip().lower())
    s = re.sub(r"\s+", " ", s).strip(" -:")
    return s


def _day(a: Artifact) -> str | None:
    return a.timestamp.strftime("%Y-%m-%d") if a.timestamp else None


def _jaccard(x: str, y: str) -> float:
    sx, sy = set(x.lower().split()), set(y.lower().split())
    if not sx or not sy:
        return 0.0
    return len(sx & sy) / len(sx | sy)


# ---------------------------------------------------------------------------
# Semantic + lexical union-find clustering
# ---------------------------------------------------------------------------
def _cluster_union(
    idxs: list[int],
    texts: dict[int, str],
    phi: float = PHI,
    tau: float = TAU,
) -> list[list[int]]:
    """Union-Find over candidate pairs: join only if sem>=phi AND jaccard>=tau."""
    if len(idxs) < 2:
        return [[i] for i in idxs] if idxs else []

    vecs = embed_texts([texts[i] for i in idxs])
    n = len(idxs)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    # cosine similarity between normalized vectors = dot product
    for i in range(n):
        vi = vecs[i]
        for j in range(i + 1, n):
            sim = sum(a * b for a, b in zip(vi, vecs[j]))
            if sim < phi:
                continue
            if _jaccard(texts[idxs[i]], texts[idxs[j]]) < tau:
                continue
            union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(idxs[i])
    return list(groups.values())


# ---------------------------------------------------------------------------
# Recurrence filter
# ---------------------------------------------------------------------------
def _filter_clusters(
    clusters: list[list[tuple[int, str]]],
    min_size: int = MIN_CLUSTER,
    min_days: int = MIN_DAYS,
    min_occurrences: int = MIN_CLUSTER,
    per_kind: bool = True,
    exclude_kinds: tuple[str, ...] = ("lead",),
) -> list[list[tuple[int, str]]]:
    """Keep clusters that recur across >= min_days distinct days.

    Args:
        clusters: list of clusters, each a list of (index, date_str_or_empty).
        min_size: minimum items in a cluster.
        min_days: minimum distinct calendar days the cluster spans.
        min_occurrences: minimum items when distinct-day counting is weak.
        per_kind: if True, evaluate each kind separately so a mixed cluster of
            unrelated items doesn't become one workflow.
        exclude_kinds: kinds to skip entirely (raw data tables like `lead`
            are not workflows).

    Returns: list of kept clusters (same shape as input).
    """
    from collections import defaultdict

    def _keep_one(items: list[tuple[int, str]]) -> bool:
        if len(items) < min_size:
            return False
        days = {d[:10] for _, d in items if d}
        if len(days) >= min_days:
            return True
        times = {d for _, d in items if d}
        return len(times) >= min_occurrences and len(days) >= 2

    kept: list[list[tuple[int, str]]] = []
    for cluster in clusters:
        if per_kind:
            buckets: dict[str, list[tuple[int, str]]] = defaultdict(list)
            for item in cluster:
                idx, _ = item
                kind = _kind_fn(idx) if _kind_fn else "unknown"
                buckets[kind].append(item)
            for kind, items in buckets.items():
                if kind in exclude_kinds:
                    continue
                if _keep_one(items):
                    kept.append(items)
        else:
            if _keep_one(cluster):
                kept.append(cluster)
    return kept


# Module-level hook so _filter_clusters can see artifact kinds without
# changing its (test-friendly) signature. Set by discover_workflows.
_kind_fn: Any = None


def _set_kind_fn(fn: Any) -> None:
    global _kind_fn
    _kind_fn = fn


# ---------------------------------------------------------------------------
# Evidence validation
# ---------------------------------------------------------------------------
def _validate_evidence(claimed: list[str], valid_ids: list[str]) -> list[str]:
    """Drop any claimed evidence id that is not in valid_ids, preserving order."""
    valid_set = set(valid_ids)
    seen: set[str] = set()
    cleaned: list[str] = []
    for cid in claimed:
        if cid in valid_set and cid not in seen:
            cleaned.append(cid)
            seen.add(cid)
    return cleaned


# ---------------------------------------------------------------------------
# Pydantic schema for the LLM's workflow naming output
# ---------------------------------------------------------------------------
class WorkflowCandidate(BaseModel):
    """What the LLM returns when asked to name a cluster as a workflow."""

    name: str = Field(description="Short plain-English name, max 6 words")
    description: str = Field(description="1-2 sentence description")
    trigger: str = Field(description="What starts this workflow")
    steps: list[str] = Field(description="Manual steps the person performs")
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    minutes_per_occurrence_estimate: int = Field(ge=0, le=480)
    time_rationale: str = Field(default="")
    automation_feasibility: str = Field(default="medium")  # high|medium|low
    feasibility_reason: str = Field(default="")
    evidence: list[str] = Field(default_factory=list)
    is_repeated_workflow: bool = Field(default=True)
    not_workflow_reason: str = Field(default="")

    @field_validator("automation_feasibility")
    @classmethod
    def _check_feasibility(cls, v: str) -> str:
        allowed = {"high", "medium", "low"}
        if v.lower() not in allowed:
            raise ValueError(f"automation_feasibility must be one of {allowed}")
        return v.lower()

    @field_validator("name")
    @classmethod
    def _check_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v


# ---------------------------------------------------------------------------
# Representative item selection (nearest to centroid)
# ---------------------------------------------------------------------------
def _representative_indices(indices: list[int], vectors: list[list[float]], k: int = 5) -> list[int]:
    import numpy as np
    if not indices:
        return []
    sub = np.asarray([vectors[i] for i in indices], dtype=float)
    centroid = sub.mean(axis=0)
    norms = np.linalg.norm(sub - centroid.reshape(1, -1), axis=1)
    order = np.argsort(norms)
    return [indices[j] for j in order[:k]]


# ---------------------------------------------------------------------------
# Workflow naming (LLM) with deterministic fallback
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = (
    "You are an expert at reading messy work artifacts (emails, spreadsheets, "
    "meeting notes) and identifying repeated, manual workflows. You are given a "
    "cluster of similar items from one person's week. Decide whether the cluster "
    "represents a real repeated workflow the person performs by hand. "
    "Only claim what the evidence supports. If the cluster is not a real repeated "
    "workflow (e.g. unrelated one-off items that happen to be similar), set "
    "is_repeated_workflow=false and return not_workflow_reason. "
    "For evidence, list ONLY the artifact ids you were given — do not invent ids."
)


def _build_cluster_prompt(
    artifacts: list[Artifact],
    cluster_ids: list[str],
    representative_ids: list[str],
    date_range: str,
) -> str:
    by_id = {a.source_ref: a for a in artifacts}
    samples = []
    for rid in representative_ids:
        a = by_id.get(rid)
        if a:
            samples.append(
                f"- id={a.source_ref} kind={a.kind} "
                f"date={a.timestamp.date() if a.timestamp else 'unknown'}\n  {a.text[:500]}"
            )
    sample_block = "\n".join(samples)
    return (
        f"Cluster size: {len(cluster_ids)} items across date range: {date_range}.\n"
        f"Representative items (5 nearest to centroid):\n{sample_block}\n\n"
        f"All artifact ids in this cluster: {', '.join(cluster_ids)}\n\n"
        "Return JSON matching the provided schema. Set evidence to a subset of "
        "the cluster artifact ids you believe support this workflow."
    )


def _fallback_candidate(cluster_ids: list[str], artifacts: list[Artifact]) -> WorkflowCandidate:
    """Deterministic fallback when the LLM fails: use the most common subject/title."""
    by_id = {a.source_ref: a for a in artifacts}
    titles = [by_id[cid].title for cid in cluster_ids if cid in by_id]
    most_common = Counter(titles).most_common(1)
    title = most_common[0][0] if most_common else "Repeated task"
    clean = re.sub(r"\s*[-–—]\s*\w+ \d+,?\s*\d{4}.*$", "", title).strip()
    clean = clean or "Repeated task"
    name = " ".join(clean.split()[:6])
    return WorkflowCandidate(
        name=name,
        description=(
            f"Repeated manual workflow inferred from {len(cluster_ids)} similar items "
            f"(fallback: LLM unavailable)."
        ),
        trigger="Similar items keep appearing in the person's inbox/notes.",
        steps=["Review items", "Perform the repeated manual action"],
        inputs=["artifact text"],
        outputs=["completed action"],
        minutes_per_occurrence_estimate=10,
        time_rationale="Default estimate; LLM naming unavailable.",
        automation_feasibility="low",
        feasibility_reason="LLM unavailable — default low feasibility.",
        evidence=cluster_ids,
        is_repeated_workflow=True,
    )


def _name_cluster(
    artifacts: list[Artifact],
    cluster_ids: list[str],
    representative_ids: list[str],
    date_range: str,
) -> WorkflowCandidate | None:
    """Call the LLM to name the cluster; fall back to a deterministic candidate."""
    try:
        user_prompt = _build_cluster_prompt(artifacts, cluster_ids, representative_ids, date_range)
        candidate = generate_json(_SYSTEM_PROMPT, user_prompt, WorkflowCandidate, retries=2)
    except LLMError as exc:
        logger.warning("LLM naming failed, using fallback: %s", exc)
        return _fallback_candidate(cluster_ids, artifacts)

    candidate.evidence = _validate_evidence(candidate.evidence, cluster_ids)
    if not candidate.evidence:
        candidate.evidence = _validate_evidence(representative_ids, cluster_ids)
    if not candidate.is_repeated_workflow:
        logger.info("LLM rejected cluster as non-workflow: %s", candidate.not_workflow_reason)
        return None
    return candidate


# ---------------------------------------------------------------------------
# Core discovery: build candidate clusters from artifacts
# ---------------------------------------------------------------------------
def _build_candidates(artifacts: list[Artifact]) -> list[list[int]]:
    """Return list of candidate clusters (index lists into `artifacts`)."""
    email_idx = [i for i, a in enumerate(artifacts) if a.kind == "email"]
    note_task_idx = [i for i, a in enumerate(artifacts) if a.kind in ("note", "task")]

    is_sent = lambda i: (json.loads(artifacts[i].raw_json or "{}").get("labels") == "sent")
    is_reply = lambda i: _subject(artifacts[i]).lower().startswith("re:")

    sent = [i for i in email_idx if is_sent(i)]
    replies = [i for i in sent if is_reply(i)]
    authored = [i for i in sent if not is_reply(i)]
    inbox = [i for i in email_idx if not is_sent(i)]

    candidates: list[list[int]] = []

    # 1) Reply threads: cluster replies by body template (looser thresholds —
    #    replies are near-verbatim, we want all variants of a template to merge).
    reply_text = {i: _cluster_text(artifacts[i]) for i in replies}
    reply_groups = [
        g for g in _cluster_union(replies, reply_text, phi=REPLY_PHI, tau=REPLY_TAU)
        if len(g) >= MIN_CLUSTER
    ]

    # Attach each inbox original to its thread (same normalized subject as a
    # reply in one of the groups). This is how inbound work counts as evidence.
    group_by_norm: dict[str, int] = {}
    for gi, g in enumerate(reply_groups):
        for i in g:
            group_by_norm[_norm_subject(_subject(artifacts[i]))] = gi

    attached: dict[int, list[int]] = {}
    for i in inbox:
        ns = _norm_subject(_subject(artifacts[i]))
        if ns in group_by_norm:
            attached.setdefault(group_by_norm[ns], []).append(i)

    for gi, g in enumerate(reply_groups):
        full = g + attached.get(gi, [])
        candidates.append(full)

    # 2) Authored emails + notes + tasks: cluster by body/text.
    cand2 = authored + note_task_idx
    text2 = {i: _cluster_text(artifacts[i]) for i in cand2}
    for g in _cluster_union(cand2, text2):
        if len(g) >= MIN_CLUSTER:
            candidates.append(g)

    # 3) Direction gate: drop pure-inbox clusters (noise with no reply link).
    final: list[list[int]] = []
    for c in candidates:
        kinds = {artifacts[i].kind for i in c}
        if kinds <= {"email"}:
            # Email-only cluster must be sent-authored (already true by
            # construction) OR contain an attached inbox member.
            if any(is_sent(i) or i in inbox for i in c):
                final.append(c)
        else:
            final.append(c)
    return final


# ---------------------------------------------------------------------------
# Persist + public API
# ---------------------------------------------------------------------------
def discover_workflows(db: Session, upload_id: int) -> list[dict[str, Any]]:
    """Run the full discovery pipeline for one upload; returns workflow dicts."""
    artifacts = (
        db.query(Artifact)
        .filter(Artifact.upload_id == upload_id)
        .order_by(Artifact.id)
        .all()
    )
    if not artifacts:
        return []

    _set_kind_fn(lambda i: artifacts[i].kind)

    raw_candidates = _build_candidates(artifacts)

    # Attach date strings + run the recurrence filter.
    dated: list[list[tuple[int, str]]] = []
    for cl in raw_candidates:
        dated.append([(i, _day(artifacts[i]) or "") for i in cl])
    kept = _filter_clusters(dated, min_size=MIN_CLUSTER, min_days=MIN_DAYS, per_kind=False)

    workflows: list[dict[str, Any]] = []
    for cluster in kept:
        indices = [i for i, _ in cluster]
        cluster_ids = [artifacts[i].source_ref for i in indices]

        # Representative ids (nearest to centroid) for the LLM prompt.
        texts = {i: _cluster_text(artifacts[i]) for i in indices}
        vecs = embed_texts([texts[i] for i in indices])
        rep_local = _representative_indices(list(range(len(indices))), vecs, k=5)
        rep_ids = [cluster_ids[r] for r in rep_local]

        dates = sorted({d for _, d in cluster if d})
        date_range = f"{dates[0]} .. {dates[-1]}" if dates else "unknown"

        candidate = _name_cluster(artifacts, cluster_ids, rep_ids, date_range)
        if candidate is None:
            continue

        # Evidence = the FULL validated cluster (so ROI/scoring sees every item).
        full_evidence = _validate_evidence(cluster_ids, cluster_ids)

        distinct_days = len({d for _, d in cluster if d})
        occurrences = max(distinct_days, 1)

        wf = Workflow(
            upload_id=upload_id,
            name=candidate.name,
            description=candidate.description,
            trigger=candidate.trigger,
            steps=json.dumps(candidate.steps),
            inputs=json.dumps(candidate.inputs),
            outputs=json.dumps(candidate.outputs),
            minutes_per_occurrence=candidate.minutes_per_occurrence_estimate,
            occurrences=occurrences,
            feasibility=candidate.automation_feasibility,
            evidence=json.dumps(full_evidence),
            status="discovered",
            low_confidence=0,
            time_rationale=candidate.time_rationale,
            feasibility_reason=candidate.feasibility_reason,
        )
        db.add(wf)
        db.flush()

        workflows.append({
            "id": wf.id,
            "upload_id": upload_id,
            "name": wf.name,
            "description": wf.description,
            "trigger": wf.trigger,
            "steps": candidate.steps,
            "minutes_per_occurrence": wf.minutes_per_occurrence,
            "occurrences": wf.occurrences,
            "feasibility": wf.feasibility,
            "evidence": full_evidence,
            "status": wf.status,
            "low_confidence": bool(wf.low_confidence),
        })

    db.commit()
    logger.info("Discovered %d workflows for upload %d", len(workflows), upload_id)
    return workflows
