"""
Severity scoring rubric.
Applies a weighted formula to classify findings into severity bands.
"""

from typing import Literal

# Severity band thresholds
SEVERITY_BANDS: list[tuple[float, str]] = [
    (90.0, "EXTREME"),   # Score >= 90 → Immediate critical risk
    (70.0, "HIGH"),      # Score 70–89 → Urgent fix needed
    (40.0, "MEDIUM"),    # Score 40–69 → Fix before next release
    (0.0,  "LOW"),       # Score < 40  → Best practice violation
]

# Scoring weights
WEIGHT_EXPLOITABILITY = 0.35  # Can it be triggered remotely?
WEIGHT_IMPACT = 0.40          # Data loss, auth bypass, service down?
WEIGHT_EXPOSURE = 0.25        # Public endpoint vs internal only?


def calculate_severity_score(
    exploitability: float,
    impact: float,
    exposure: float,
) -> float:
    """
    Calculate a weighted severity score.

    Args:
        exploitability: 0.0–100.0 — How easily can this be triggered remotely?
        impact: 0.0–100.0 — What damage can it cause? (data loss, auth bypass, etc.)
        exposure: 0.0–100.0 — Is it on a public endpoint or internal only?

    Returns:
        Weighted score 0.0–100.0
    """
    score = (
        exploitability * WEIGHT_EXPLOITABILITY +
        impact * WEIGHT_IMPACT +
        exposure * WEIGHT_EXPOSURE
    )
    return round(min(max(score, 0.0), 100.0), 1)


def score_to_severity(score: float) -> Literal["EXTREME", "HIGH", "MEDIUM", "LOW"]:
    """
    Map a numeric score to a severity band.

    Args:
        score: 0.0–100.0 severity score

    Returns:
        Severity classification: "EXTREME", "HIGH", "MEDIUM", or "LOW"
    """
    for threshold, severity in SEVERITY_BANDS:
        if score >= threshold:
            return severity  # type: ignore
    return "LOW"


def get_severity_emoji(severity: str) -> str:
    """Get the emoji indicator for a severity level."""
    return {
        "EXTREME": "🔴",
        "HIGH": "🟠",
        "MEDIUM": "🟡",
        "LOW": "🔵",
    }.get(severity, "⚪")


def get_severity_order(severity: str) -> int:
    """Get numeric ordering for severity (lower = more severe, for sorting)."""
    return {
        "EXTREME": 0,
        "HIGH": 1,
        "MEDIUM": 2,
        "LOW": 3,
    }.get(severity, 4)
