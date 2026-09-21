"""Rules 68-71: the ORB+ICC execution layer, as real computation.

The report used to just print a reminder sentence ("no entry without an
ORB break..."). That's not a check -- it's a hope that whoever's reading
the report does the math themselves. This actually computes the opening
range and tests whether a valid breakout happened, and whether it went
anywhere afterward, from real bar data.

Confirmed against real Sept 21, 2026 data: HOOD, MSTR, and COIN were all
called CALL, but on all three the day's high was set *during* the 9:30-9:45
opening range itself -- no bar ever closed above that range again, so no
valid entry (rule 70) ever formed. AMD, one of the tickers that actually
worked that day, broke its opening-range high within the first post-ORB
bar and kept making new highs into the close.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

ORB_MINUTES = 15


def _parse_ts(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


@dataclass
class OrbResult:
    orb_high: float
    orb_low: float
    breakout_confirmed: bool
    breakout_ts: Optional[str]
    breakout_close: Optional[float]
    sustained: bool
    max_follow_through: Optional[float]
    reasons: list


def compute_orb_and_breakout(
    bars: list[dict],
    open_ts: str,
    side: str,
    sustained_follow_through_fraction: float = 0.003,
) -> OrbResult:
    """`bars` are regular-session bars (any order; sorted here by ts).
    `side` is the locked CALL/PUT forecast -- MIXED has nothing to execute
    on (rule 68: direction and execution are separate)."""
    sorted_bars = sorted(bars, key=lambda b: b["ts"])
    open_dt = _parse_ts(open_ts)
    orb_end = open_dt.timestamp() + ORB_MINUTES * 60

    orb_bars = [b for b in sorted_bars if open_dt.timestamp() <= _parse_ts(b["ts"]).timestamp() < orb_end]
    after_bars = [b for b in sorted_bars if _parse_ts(b["ts"]).timestamp() >= orb_end]

    if not orb_bars:
        return OrbResult(0.0, 0.0, False, None, None, False, None, ["no bars in the 9:30-9:45 opening range"])

    orb_high = max(b["high"] for b in orb_bars)
    orb_low = min(b["low"] for b in orb_bars)

    if side not in ("CALL", "PUT"):
        return OrbResult(orb_high, orb_low, False, None, None, False, None, ["side is MIXED -- no execution to check (rule 68)"])

    breakout_ts = breakout_close = None
    for b in after_bars:
        if side == "CALL" and b["close"] > orb_high:
            breakout_ts, breakout_close = b["ts"], b["close"]
            break
        if side == "PUT" and b["close"] < orb_low:
            breakout_ts, breakout_close = b["ts"], b["close"]
            break

    if breakout_ts is None:
        boundary = "high" if side == "CALL" else "low"
        return OrbResult(
            orb_high, orb_low, False, None, None, False, None,
            [f"no bar closed beyond the ORB {boundary} ({orb_high if side == 'CALL' else orb_low}) all "
             f"session -- no valid entry ever formed (rule 70); the day's extreme was set inside the "
             f"opening range itself"],
        )

    later_bars = [b for b in after_bars if b["ts"] > breakout_ts]
    if side == "CALL":
        max_follow_through = max((b["close"] - breakout_close for b in later_bars), default=0.0)
    else:
        max_follow_through = max((breakout_close - b["close"] for b in later_bars), default=0.0)

    sustained = bool(breakout_close) and max_follow_through >= breakout_close * sustained_follow_through_fraction
    reasons = (
        [f"broke out at {breakout_ts} and continued at least {sustained_follow_through_fraction:.1%} further afterward"]
        if sustained
        else [f"broke out at {breakout_ts} but never continued -- likely chopped back inside the ORB range"]
    )
    return OrbResult(orb_high, orb_low, True, breakout_ts, breakout_close, sustained, max_follow_through, reasons)
