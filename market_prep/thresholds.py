"""Numeric thresholds for the deterministic layer.

The rulebook requires determinism (rule 24) but never specifies the actual
numbers, which is why "determinism" was never real in the chat-based
version. These are first-pass, documented calibrations -- not validated
against forward results yet. Per rule 84/85, change them only after the
daily log (market_prep/store.py) has enough scored sessions to show a
repeated pattern, not after one bad day and not by fitting a known winner.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Thresholds:
    # Rule 9: price-conflict threshold between two sources (fraction, not %).
    price_conflict_fraction: float = 0.0005

    # Rule 9/52/53: how old fetched data can be (seconds before cutoff) and
    # still count as synchronized/HIGH confidence.
    stale_data_max_age_seconds: float = 120.0

    # Minimum premarket move, as a fraction of the ticker's own 14d ATR,
    # required to call Stage 1 UP/DOWN instead of MIXED. Prevents noise-level
    # moves from being classified as directional.
    min_move_atr_fraction: float = 0.15

    # Retention (rule 22): fraction of the premarket extreme move still held
    # at the cutoff. >= strong counts as "low giveback"; <= weak counts as
    # "meaningful giveback".
    retention_strong: float = 0.70
    retention_weak: float = 0.40

    # Range position (rule 14): 0 = at the premarket low, 1 = at the
    # premarket high. "Near extreme" means within this fraction of either
    # end, in the direction of the Stage 1 state.
    range_position_near_extreme: float = 0.85

    # Extension classification (rule 29), in multiples of 14d ATR.
    extension_normal_max_atr_multiple: float = 1.0
    extension_elevated_max_atr_multiple: float = 2.0
    # > extension_elevated_max_atr_multiple => EXTREME

    # Participation trend (rule 39): ratio of final-segment volume rate to
    # middle-segment volume rate.
    participation_accelerating_ratio: float = 1.15
    participation_decelerating_ratio: float = 0.85

    # Continuation / fade routes (rules 26/27, trimmed per Sept-18
    # amendment to ~5 checks each): how many of the 5 checks must be true.
    continuation_checks_required: int = 3
    fade_checks_required: int = 3

    # Head-to-head separation label (rules 59/60): score gap that counts as
    # a CLEAR win for #1 vs NARROW.
    head_to_head_clear_gap: float = 1.0


DEFAULT_THRESHOLDS = Thresholds()
