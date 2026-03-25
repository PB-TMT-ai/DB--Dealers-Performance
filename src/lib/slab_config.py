"""Slab thresholds and derived-column logic (pure functions)."""

from __future__ import annotations

# Ordered ascending — each tuple is (min_volume_inclusive, slab_label)
SLAB_THRESHOLDS: list[tuple[float, str]] = [
    (200, "A"),
    (300, "B"),
    (500, "C"),
    (750, "D"),
    (1250, "E"),
]

SLAB_ORDER: list[str] = ["No Slab", "A", "B", "C", "D", "E"]


def determine_slab(fy26_total: float) -> str:
    """Return the qualified slab for a given FY26 total volume (MT)."""
    slab = "No Slab"
    for threshold, label in SLAB_THRESHOLDS:
        if fy26_total >= threshold:
            slab = label
        else:
            break
    return slab


def determine_next_slab(current_slab: str) -> str:
    """Return the slab one step above *current_slab*. E stays E."""
    try:
        idx = SLAB_ORDER.index(current_slab)
    except ValueError:
        return "A"
    if idx >= len(SLAB_ORDER) - 1:
        return "E"
    return SLAB_ORDER[idx + 1]


def volume_to_next_slab(fy26_total: float, current_slab: str) -> float:
    """Return volume needed to reach the next slab threshold."""
    if current_slab == "E":
        return 0.0
    next_slab = determine_next_slab(current_slab)
    for threshold, label in SLAB_THRESHOLDS:
        if label == next_slab:
            return max(0.0, threshold - fy26_total)
    # Fallback: if current is No Slab, need 200
    return max(0.0, 200.0 - fy26_total)


def count_lifting_frequency(month_values: list[float]) -> int:
    """Count non-zero month values (0–12)."""
    return sum(1 for v in month_values if v and v > 0)
