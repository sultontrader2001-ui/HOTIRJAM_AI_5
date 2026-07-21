"""Entry timing classification rules (Sprint 37) — audit only.

Rules (deterministic, documented):

EARLY
  Immediate adverse excursion, then favorable recovery by 5 minutes.
  MAE <= -EARLY_ADVERSE_MIN AND MFE >= EARLY_RECOVERY_MIN AND points_5m > 0

LATE
  Little favorable follow-through after entry (move largely exhausted).
  MFE < LATE_MFE_MAX AND points_5m <= LATE_FOLLOWTHROUGH_MAX

NORMAL
  Price continues in the signal direction after entry.
  points_5m > 0 AND MFE >= abs(MAE) AND not EARLY

INCONCLUSIVE
  Everything else (flat, mixed, incomplete evidence).
"""

from __future__ import annotations

from hotirjam_ai5.entry_timing.models import CheckpointSample, TimingClass

# Classification thresholds (points). Audit constants — not Trade Decision thresholds.
EARLY_ADVERSE_MIN: float = 2.0
EARLY_RECOVERY_MIN: float = 2.0
LATE_MFE_MAX: float = 3.0
LATE_FOLLOWTHROUGH_MAX: float = 2.0


def signed_points(*, decision: str, entry_price: float, current_price: float) -> float:
    """BUY: current − entry. SELL: entry − current."""
    if decision == "SELL_INTERNAL":
        return entry_price - current_price
    return current_price - entry_price


def classify_timing(
    *,
    mfe: float,
    mae: float,
    checkpoints: tuple[CheckpointSample, ...] | list[CheckpointSample],
) -> tuple[TimingClass, str]:
    """Classify entry timing from completed 5-minute path statistics."""
    points_5m = _points_at(checkpoints, 300)
    if points_5m is None:
        return (
            TimingClass.INCONCLUSIVE,
            "5-minute checkpoint missing; cannot classify.",
        )

    # EARLY: immediate adverse, then recovery.
    if (
        mae <= -EARLY_ADVERSE_MIN
        and mfe >= EARLY_RECOVERY_MIN
        and points_5m > 0
    ):
        return (
            TimingClass.EARLY,
            (
                f"Immediate adverse excursion (MAE {mae:.2f}) then favorable "
                f"recovery (MFE {mfe:.2f}, 5m {points_5m:+.2f})."
            ),
        )

    # LATE: weak follow-through after entry.
    if mfe < LATE_MFE_MAX and points_5m <= LATE_FOLLOWTHROUGH_MAX:
        return (
            TimingClass.LATE,
            (
                f"Limited follow-through after entry "
                f"(MFE {mfe:.2f}, 5m {points_5m:+.2f}); "
                "most of the move likely occurred before the signal."
            ),
        )

    # NORMAL: continues strongly in signal direction.
    if points_5m > 0 and mfe >= abs(mae):
        return (
            TimingClass.NORMAL,
            (
                f"Price continued in signal direction "
                f"(5m {points_5m:+.2f}, MFE {mfe:.2f} ≥ |MAE| {abs(mae):.2f})."
            ),
        )

    return (
        TimingClass.INCONCLUSIVE,
        (
            f"Mixed path (5m {points_5m:+.2f}, MFE {mfe:.2f}, MAE {mae:.2f}); "
            "does not match EARLY / NORMAL / LATE rules."
        ),
    )


def _points_at(
    checkpoints: tuple[CheckpointSample, ...] | list[CheckpointSample],
    offset_seconds: int,
) -> float | None:
    for sample in checkpoints:
        if sample.offset_seconds == offset_seconds:
            return sample.points
    return None
