"""Phase 4 tests: ROI ranking formulas (pure functions)."""
from __future__ import annotations

import math

from app.services.roi import (
    AUTOMATION_COVERAGE,
    feasibility_bonus,
    hours_saved_per_week,
    occurrences_per_week,
    priority_score,
    score_workflows,
    total_hours_saved_per_week,
)


def test_occurrences_per_week_scales_to_seven_day_week() -> None:
    # 1 occurrence in a 5-day window -> 1/5*7 = 1.4 per week
    assert occurrences_per_week(1, 5) == 1.4
    # 5 occurrences across 5 days -> 7 per week
    assert occurrences_per_week(5, 5) == 7.0
    # 3 occurrences across 3 days -> 7 per week
    assert math.isclose(occurrences_per_week(3, 3), 7.0)


def test_occurrences_per_week_zero_and_guard() -> None:
    assert occurrences_per_week(0, 5) == 0.0
    # Zero/unknown window is guarded (no divide-by-zero).
    assert occurrences_per_week(3, 0) == 0.0


def test_hours_formula_exact() -> None:
    # hours = occurrences_per_week * minutes * coverage / 60
    assert math.isclose(hours_saved_per_week(7.0, 15, "high"), 7.0 * 15 * 0.9 / 60)
    assert math.isclose(hours_saved_per_week(7.0, 15, "medium"), 7.0 * 15 * 0.6 / 60)
    assert math.isclose(hours_saved_per_week(7.0, 15, "low"), 7.0 * 15 * 0.3 / 60)


def test_hours_zero_edge_cases() -> None:
    assert hours_saved_per_week(0.0, 15, "high") == 0.0
    assert hours_saved_per_week(7.0, 0, "high") == 0.0
    assert hours_saved_per_week(7.0, 0, "low") == 0.0


def test_low_feasibility_reduces_hours() -> None:
    assert hours_saved_per_week(7.0, 15, "low") < hours_saved_per_week(7.0, 15, "high")
    assert AUTOMATION_COVERAGE == {"high": 0.9, "medium": 0.6, "low": 0.3}


def test_priority_orders_by_hours_then_feasibility() -> None:
    # Same hours, higher feasibility -> higher priority.
    assert priority_score(1.0, "high") > priority_score(1.0, "low")
    # More hours wins even at lower feasibility.
    assert priority_score(3.0, "low") > priority_score(0.5, "high")


def test_total_sums_across_workflows() -> None:
    total = total_hours_saved_per_week([1.05, 0.525, 1.575])
    assert math.isclose(total, 3.15)
    assert total_hours_saved_per_week([]) == 0.0


def test_feasibility_bonus_bounded() -> None:
    assert feasibility_bonus("high") > feasibility_bonus("medium") > feasibility_bonus("low")
    assert feasibility_bonus("unknown") == 0.0


def test_score_workflows_sorts_desc_and_explains() -> None:
    rows = [
        {"id": 1, "name": "Low", "minutes_per_occurrence": 10,
         "occurrences": 5, "feasibility": "low"},
        {"id": 2, "name": "High", "minutes_per_occurrence": 25,
         "occurrences": 5, "feasibility": "high"},
        {"id": 3, "name": "Zero", "minutes_per_occurrence": 0,
         "occurrences": 5, "feasibility": "high"},
    ]
    scored = score_workflows(rows, window_days=5)
    ids = [r["id"] for r in scored]
    assert ids == [2, 1, 3], f"unexpected order {ids}"
    # Every row carries a human-readable explanation.
    for r in scored:
        assert "h/week" in r["roi_explanation"]
        assert r["hours_saved_per_week"] >= 0
