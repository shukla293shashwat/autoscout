"""Phase 4: ROI scoring and ranking.

hours_saved_per_week = occurrences_per_week * minutes_per_occurrence
                        * automation_coverage / 60

automation_coverage = 0.9 (high), 0.6 (medium), 0.3 (low)

occurrences_per_week scales the occurrences detected in the data window to a
7-day week. priority_score combines hours_saved_per_week with a bounded
feasibility bonus so that, all else equal, more-automatable work ranks higher,
and a short human-readable explanation is produced for the UI.
"""
from __future__ import annotations

from typing import Any, Iterable

AUTOMATION_COVERAGE: dict[str, float] = {"high": 0.9, "medium": 0.6, "low": 0.3}

# Bounded feasibility bonus (kept small so hours remain the dominant signal).
_FEASIBILITY_BONUS: dict[str, float] = {"high": 0.25, "medium": 0.10, "low": 0.0}
_DEFAULT_WINDOW_DAYS = 7


def coverage(feasibility: str) -> float:
    """Return the automation-coverage factor for a feasibility level."""
    return AUTOMATION_COVERAGE.get(feasibility.lower().strip(), AUTOMATION_COVERAGE["low"])


def occurrences_per_week(occurrences: int, window_days: int) -> float:
    """Scale occurrences detected in the window to a full 7-day week."""
    if occurrences <= 0 or window_days <= 0:
        return 0.0
    return round(occurrences / window_days * 7.0, 4)


def hours_saved_per_week(opw: float, minutes: int, feasibility: str) -> float:
    """Hours saved per week for a single workflow."""
    if opw <= 0 or minutes <= 0:
        return 0.0
    return opw * minutes * coverage(feasibility) / 60.0


def feasibility_bonus(feasibility: str) -> float:
    """Small additive bonus that breaks ties toward more-automatable work."""
    return _FEASIBILITY_BONUS.get(feasibility.lower().strip(), 0.0)


def priority_score(hours: float, feasibility: str) -> float:
    """Combined ranking score: hours saved + bounded feasibility bonus."""
    return round(hours + feasibility_bonus(feasibility), 4)


def _explanation(opw: float, minutes: int, feas: str, hours: float) -> str:
    """Human-readable one-line ROI explanation."""
    if minutes <= 0 or hours <= 0:
        return (
            f"No measurable time saved (0 h/week): missing time estimate "
            f"(~{opw:.0f} occurrences x {minutes} min, {feas} feasibility)"
        )
    cov = int(coverage(feas) * 100)
    return (
        f"Saves about {hours:.1f} h/week: ~{opw:.0f} occurrences x {minutes} min, "
        f"{feas} feasibility ({cov}% automatable)"
    )


def score_workflows(
    rows: Iterable[dict[str, Any]],
    window_days: int = _DEFAULT_WINDOW_DAYS,
) -> list[dict[str, Any]]:
    """Score and sort workflow dicts by priority_score (descending).

    Each input row must have: minutes_per_occurrence, occurrences, feasibility.
    Adds: occurrences_per_week, hours_saved_per_week, priority_score,
    roi_explanation. Pure — returns new dicts.
    """
    scored: list[dict[str, Any]] = []
    for row in rows:
        opw = occurrences_per_week(int(row.get("occurrences", 0) or 0), window_days)
        minutes = int(row.get("minutes_per_occurrence", 0) or 0)
        feas = str(row.get("feasibility", "low"))
        hours = hours_saved_per_week(opw, minutes, feas)
        priority = priority_score(hours, feas)
        out = dict(row)
        out["occurrences_per_week"] = round(opw, 4)
        out["hours_saved_per_week"] = round(hours, 4)
        out["priority_score"] = priority
        out["roi_explanation"] = _explanation(opw, minutes, feas, hours)
        scored.append(out)
    scored.sort(key=lambda r: r["priority_score"], reverse=True)
    return scored


def total_hours_saved_per_week(rows: Iterable[Any]) -> float:
    """Sum hours_saved_per_week across workflow rows (dicts or plain floats)."""
    total = 0.0
    for r in rows:
        if isinstance(r, dict):
            total += float(r.get("hours_saved_per_week", 0) or 0)
        else:
            total += float(r or 0)
    return round(total, 4)
