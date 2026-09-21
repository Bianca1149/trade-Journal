"""Pure, deterministic math over a ticker's premarket bar data.

Every function here takes plain data (numbers / dicts) and returns plain
data. No LLM judgment, no network calls -- same input always produces the
same output, which is the actual point (rule 24).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


def _parse_ts(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def data_age_seconds(fetched_at: str, cutoff_ts: str) -> float:
    """How stale a fetch was relative to the analysis cutoff (rule 5)."""
    return abs((_parse_ts(cutoff_ts) - _parse_ts(fetched_at)).total_seconds())


def price_conflict(price_a: float, price_b: Optional[float], threshold_fraction: float) -> bool:
    """Rule 9: True if two source prices disagree by more than the threshold."""
    if price_b is None or price_a == 0:
        return False
    return abs(price_a - price_b) / abs(price_a) > threshold_fraction


def vwap(bars: list[dict]) -> Optional[float]:
    """Volume-weighted average price over the given bars (rule 15)."""
    total_pv = 0.0
    total_v = 0.0
    for bar in bars:
        typical = (bar["high"] + bar["low"] + bar["close"]) / 3.0
        total_pv += typical * bar["volume"]
        total_v += bar["volume"]
    if total_v == 0:
        return None
    return total_pv / total_v


def premarket_range(bars: list[dict]) -> tuple[Optional[float], Optional[float]]:
    """(low, high) across the premarket bars (rule 14)."""
    if not bars:
        return None, None
    return min(b["low"] for b in bars), max(b["high"] for b in bars)


def range_position(last_price: float, low: Optional[float], high: Optional[float]) -> Optional[float]:
    """0 = at the premarket low, 1 = at the premarket high (rule 14)."""
    if low is None or high is None or high == low:
        return None
    return (last_price - low) / (high - low)


def extreme_in_direction(bars: list[dict], prior_close: float) -> Optional[float]:
    """The premarket price furthest from prior_close, signed toward the net move.

    Used as the "extreme" endpoint for retention/giveback (rule 22): if the
    ticker moved up overall, this is the premarket high; if down, the low.
    """
    if not bars:
        return None
    net_up = (bars[-1]["close"] - prior_close) >= 0
    return max(b["high"] for b in bars) if net_up else min(b["low"] for b in bars)


def retention(last_price: float, prior_close: float, extreme: Optional[float]) -> Optional[float]:
    """Fraction of the premarket extreme move still held at cutoff (rule 22).

    1.0 = fully retained (last_price == extreme), 0.0 = fully given back
    (last_price == prior_close). Can exceed 1.0 if price pushed past the
    recorded extreme after the extreme was set, or go negative if price
    reversed through prior_close.
    """
    if extreme is None or extreme == prior_close:
        return None
    return (last_price - prior_close) / (extreme - prior_close)


def atr_normalized_displacement(last_price: float, prior_close: float, atr_14d: float) -> Optional[float]:
    """Signed premarket displacement in multiples of the ticker's own ATR (rule 20)."""
    if not atr_14d:
        return None
    return (last_price - prior_close) / atr_14d


def classify_extension(displacement_atr_multiples: Optional[float], thresholds) -> str:
    """NORMAL / ELEVATED / EXTREME relative to the ticker's own volatility (rule 29)."""
    if displacement_atr_multiples is None:
        return "NORMAL"
    magnitude = abs(displacement_atr_multiples)
    if magnitude <= thresholds.extension_normal_max_atr_multiple:
        return "NORMAL"
    if magnitude <= thresholds.extension_elevated_max_atr_multiple:
        return "ELEVATED"
    return "EXTREME"


def _segment_volume_rate(bars: list[dict]) -> float:
    if not bars:
        return 0.0
    span_minutes = max(
        1.0,
        (_parse_ts(bars[-1]["ts"]) - _parse_ts(bars[0]["ts"])).total_seconds() / 60.0,
    )
    return sum(b["volume"] for b in bars) / span_minutes


def participation_trend(bars: list[dict], thresholds) -> str:
    """accelerating / stable / decelerating / unavailable (rules 39-41).

    Splits the premarket bars into three equal-length segments (early,
    middle, final) and compares the final segment's volume rate to the
    middle segment's. Marked unavailable rather than guessed when there
    isn't enough data (rule 41 -- never auto-penalize for its absence).
    """
    if len(bars) < 6:
        return "unavailable"
    third = len(bars) // 3
    early, middle, final = bars[:third], bars[third : 2 * third], bars[2 * third :]
    if not middle or not final:
        return "unavailable"
    middle_rate = _segment_volume_rate(middle)
    final_rate = _segment_volume_rate(final)
    if middle_rate == 0:
        return "unavailable"
    ratio = final_rate / middle_rate
    if ratio >= thresholds.participation_accelerating_ratio:
        return "accelerating"
    if ratio <= thresholds.participation_decelerating_ratio:
        return "decelerating"
    return "stable"


def latest_window_progressing(bars: list[dict], direction_up: bool, window: int = 5) -> Optional[bool]:
    """Whether the most recent bars are still moving in the Stage-1 direction (rule 21/23)."""
    if len(bars) < window + 1:
        return None
    recent = bars[-window:]
    closes = [b["close"] for b in recent]
    net_move = closes[-1] - closes[0]
    return (net_move > 0) if direction_up else (net_move < 0)
