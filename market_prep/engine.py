"""Stage 1 / Stage 2 classification, data confidence, and the rule-55
ranking hierarchy -- as actual code instead of an LLM holding 22 rows of
judgment in its head.

Input contract (one dict per ticker, see schema.md for the full spec):

    {
      "ticker": "HOOD",
      "prior_close": 41.20,
      "premarket_bars": [{"ts": "...", "open":..,"high":..,"low":..,"close":..,"volume":..}, ...],
      "last_price": 43.10,
      "last_price_ts": "2026-09-21T13:59:40Z",
      "fetched_at": "2026-09-21T13:59:45Z",
      "cutoff_ts": "2026-09-21T14:00:00Z",
      "atr_14d": 1.35,
      "secondary_last_price": 43.09,        # optional, for price-conflict check
      "data_missing": false,                 # true = Webull query failed/empty (rule: auto INSUFFICIENT)
      "fresh_catalyst": true,
      "catalyst_price_confirmed": true,
      "cluster_aligned": true,
      "driver_aligned": false,
      "sector_breadth_supportive": true,
      "prior_regime_aligned": true,          # True/False/None (None = not applicable / unresolved)
      "rs_rw_normalized": 0.42               # signed ATR-normalized RS/RW vs benchmark, or None
    }
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from . import metrics, orb
from .thresholds import Thresholds, DEFAULT_THRESHOLDS

GRADE_ORDER = ["A-", "A", "B-", "B", "B+", "C", "MIXED"]  # not used directly; see grade()


@dataclass
class Stage1Result:
    state: str  # UP / DOWN / MIXED
    displacement_atr: Optional[float]
    extension: str  # NORMAL / ELEVATED / EXTREME
    range_position: Optional[float]
    retention: Optional[float]
    vwap_price: Optional[float]
    vwap_relation: Optional[str]  # above / below / unavailable
    reasons: list[str] = field(default_factory=list)


@dataclass
class Stage2Result:
    route: str  # CONTINUATION / FADE / MIXED
    continuation_checks: dict
    fade_checks: dict
    reasons: list[str] = field(default_factory=list)


@dataclass
class ConfidenceResult:
    level: str  # HIGH / REDUCED / INSUFFICIENT
    reasons: list[str] = field(default_factory=list)


@dataclass
class TickerRow:
    ticker: str
    stage1: Stage1Result
    stage2: Stage2Result
    confidence: ConfidenceResult
    side: str  # CALL / PUT / MIXED
    grade: str
    elevated_open_reversal_risk: bool
    rank_key: tuple
    rank_components: dict


def classify_stage1(snap: dict, thresholds: Thresholds = DEFAULT_THRESHOLDS) -> Stage1Result:
    bars = snap.get("premarket_bars") or []
    prior_close = snap["prior_close"]
    last_price = snap["last_price"]
    atr = snap.get("atr_14d")

    displacement_atr = metrics.atr_normalized_displacement(last_price, prior_close, atr) if atr else None
    extension = metrics.classify_extension(displacement_atr, thresholds)

    low, high = metrics.premarket_range(bars)
    rpos = metrics.range_position(last_price, low, high)

    extreme = metrics.extreme_in_direction(bars, prior_close)
    ret = metrics.retention(last_price, prior_close, extreme)

    vwap_price = metrics.vwap(bars) if bars else None
    vwap_relation = None
    if vwap_price is not None:
        vwap_relation = "above" if last_price >= vwap_price else "below"

    reasons = []
    if displacement_atr is None or abs(displacement_atr) < thresholds.min_move_atr_fraction:
        state = "MIXED"
        reasons.append(
            f"displacement {displacement_atr!r} ATR-multiples below min_move_atr_fraction="
            f"{thresholds.min_move_atr_fraction}"
        )
    else:
        state = "UP" if displacement_atr > 0 else "DOWN"
        reasons.append(f"displacement={displacement_atr:.3f} ATR multiples -> {state}")

    return Stage1Result(
        state=state,
        displacement_atr=displacement_atr,
        extension=extension,
        range_position=rpos,
        retention=ret,
        vwap_price=vwap_price,
        vwap_relation=vwap_relation,
        reasons=reasons,
    )


def classify_stage2(snap: dict, stage1: Stage1Result, thresholds: Thresholds = DEFAULT_THRESHOLDS) -> Stage2Result:
    bars = snap.get("premarket_bars") or []
    direction_up = stage1.state == "UP"

    if stage1.state == "MIXED":
        return Stage2Result(
            route="MIXED",
            continuation_checks={},
            fade_checks={},
            reasons=["Stage 1 state is MIXED -> Stage 2 route is MIXED (no directional forecast to test)"],
        )

    # --- Continuation checks (rule 26, trimmed to 5) ---
    rpos = stage1.range_position
    near_extreme = (
        rpos is not None
        and (
            (direction_up and rpos >= thresholds.range_position_near_extreme)
            or (not direction_up and rpos <= 1 - thresholds.range_position_near_extreme)
        )
    )
    low_giveback = stage1.retention is not None and stage1.retention >= thresholds.retention_strong
    progressing = metrics.latest_window_progressing(bars, direction_up)
    catalyst_or_cluster = bool(
        (snap.get("fresh_catalyst") and snap.get("catalyst_price_confirmed"))
        or snap.get("cluster_aligned")
        or snap.get("driver_aligned")
    )
    participation = metrics.participation_trend(bars, thresholds)
    participation_supportive = participation in ("accelerating", "stable") and progressing is not False

    continuation_checks = {
        "holding_near_extreme": near_extreme,
        "low_giveback": low_giveback,
        "latest_window_progressing": bool(progressing),
        "catalyst_or_cluster_or_driver": catalyst_or_cluster,
        "participation_supportive": participation_supportive,
    }

    # --- Fade checks (rule 27, trimmed to 5) ---
    late_stall_or_reversal = progressing is False
    meaningful_giveback = stage1.retention is not None and stage1.retention <= thresholds.retention_weak
    weak_range_position = rpos is not None and not near_extreme
    lost_vwap_acceptance = (
        stage1.vwap_relation is not None
        and ((direction_up and stage1.vwap_relation == "below") or (not direction_up and stage1.vwap_relation == "above"))
    )
    no_confirmation_for_outsized_move = stage1.extension in ("ELEVATED", "EXTREME") and not catalyst_or_cluster

    fade_checks = {
        "late_stall_or_reversal": late_stall_or_reversal,
        "meaningful_giveback": meaningful_giveback,
        "weak_range_position": weak_range_position,
        "lost_vwap_acceptance": lost_vwap_acceptance,
        "no_confirmation_for_outsized_move": no_confirmation_for_outsized_move,
    }

    continuation_count = sum(continuation_checks.values())
    fade_count = sum(fade_checks.values())
    # Rule 27: fade needs at least one real price/structure signal, not just
    # "no confirmation" on its own.
    fade_has_structure_signal = late_stall_or_reversal or meaningful_giveback

    reasons = [
        f"continuation_count={continuation_count}/5, fade_count={fade_count}/5, "
        f"fade_has_structure_signal={fade_has_structure_signal}"
    ]

    if fade_count >= thresholds.fade_checks_required and fade_has_structure_signal and fade_count > continuation_count:
        route = "FADE"
    elif continuation_count >= thresholds.continuation_checks_required and continuation_count > fade_count:
        route = "CONTINUATION"
    else:
        route = "MIXED"

    return Stage2Result(route=route, continuation_checks=continuation_checks, fade_checks=fade_checks, reasons=reasons)


def classify_confidence(snap: dict, thresholds: Thresholds = DEFAULT_THRESHOLDS) -> ConfidenceResult:
    reasons = []

    if snap.get("data_missing"):
        return ConfidenceResult(level="INSUFFICIENT", reasons=["premarket data query failed/empty (auto INSUFFICIENT)"])

    if not snap.get("premarket_bars"):
        return ConfidenceResult(level="INSUFFICIENT", reasons=["no premarket bars present"])

    level = "HIGH"

    age = metrics.data_age_seconds(snap["fetched_at"], snap["cutoff_ts"])
    if age > thresholds.stale_data_max_age_seconds:
        level = "REDUCED"
        reasons.append(f"fetched_at is {age:.0f}s from cutoff (> {thresholds.stale_data_max_age_seconds}s)")

    if metrics.price_conflict(snap["last_price"], snap.get("secondary_last_price"), thresholds.price_conflict_fraction):
        level = "REDUCED"
        reasons.append("unresolved price conflict between primary and secondary source (rule 9)")

    if snap.get("atr_14d") is None:
        level = "REDUCED"
        reasons.append("atr_14d missing -> extension/displacement not computable")

    if not reasons:
        reasons.append("fresh, synchronized, no conflicts")

    return ConfidenceResult(level=level, reasons=reasons)


def side_from_route(state: str, route: str) -> str:
    """Rule 3 directional mapping."""
    if route == "MIXED" or state == "MIXED":
        return "MIXED"
    if state == "UP":
        return "CALL" if route == "CONTINUATION" else "PUT"
    return "PUT" if route == "CONTINUATION" else "CALL"


def grade(stage2: Stage2Result, confidence: ConfidenceResult) -> str:
    """A-/B+/B/B-/C/MIXED from the check counts. First-pass buckets --
    recalibrate from logged forward results (rule 84), not on a whim."""
    if stage2.route == "MIXED":
        return "MIXED"
    checks = stage2.continuation_checks if stage2.route == "CONTINUATION" else stage2.fade_checks
    count = sum(checks.values())
    if confidence.level == "INSUFFICIENT":
        return "MIXED"
    if count >= 5:
        return "A-"
    if count == 4:
        return "B+"
    if count == 3:
        return "B" if confidence.level == "HIGH" else "B-"
    return "C"


def elevated_open_reversal_risk(snap: dict, stage1: Stage1Result, thresholds: Thresholds = DEFAULT_THRESHOLDS) -> bool:
    """Sept-21 amendment: large move, no fresh catalyst, already at the
    premarket extreme -- flagged separately from the Directional Grade.

    "Large" is ATR-elevated/extreme OR a raw-percent move past
    large_move_pct_floor. The percent leg exists because a ticker with an
    already-large own ATR (e.g. HOOD at ~7.2 after a volatile two weeks)
    can put in a real, reversal-prone premarket move that still reads
    NORMAL on ATR-normalized extension alone -- confirmed against the real
    Sept 21, 2026 HOOD case (see tests/test_hood_reversal_case.py), where
    the ATR-only version of this check missed it and HOOD round-tripped
    from the premarket high in the first 45 minutes after the open.
    """
    near_extreme = (
        stage1.range_position is not None
        and (stage1.range_position >= thresholds.range_position_near_extreme or stage1.range_position <= 1 - thresholds.range_position_near_extreme)
    )
    no_fresh_catalyst = not (snap.get("fresh_catalyst") and snap.get("catalyst_price_confirmed"))
    pct_move = 0.0
    if snap.get("prior_close"):
        pct_move = abs(snap["last_price"] - snap["prior_close"]) / snap["prior_close"]
    large_move = stage1.extension in ("ELEVATED", "EXTREME") or pct_move >= thresholds.large_move_pct_floor
    return large_move and no_fresh_catalyst and near_extreme


def rank_key(
    snap: dict,
    stage1: Stage1Result,
    stage2: Stage2Result,
    confidence: ConfidenceResult,
    elevated_risk: bool,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
) -> tuple[tuple, dict]:
    """Rule 55 priority order, plus the three Sept-21 same-day amendments.

    Returns a tuple sortable descending (higher = better) plus a dict of the
    named components for the report/debugging.
    """
    checks = stage2.continuation_checks if stage2.route == "CONTINUATION" else stage2.fade_checks
    dominant_count = sum(checks.values()) if checks else 0
    opposite_count = (
        sum(stage2.fade_checks.values())
        if stage2.route == "CONTINUATION"
        else sum(stage2.continuation_checks.values())
    )
    clarity = dominant_count - opposite_count  # 1. clarity of continuation vs fade

    quality = 0.0  # 2. quality of late acceptance/retention or fade evidence
    if stage1.retention is not None:
        quality = stage1.retention if stage2.route == "CONTINUATION" else (1 - stage1.retention)

    prior_regime = {True: 1, None: 0, False: -1}.get(snap.get("prior_regime_aligned"), 0)  # 3

    cluster = 1 if (snap.get("cluster_aligned") or snap.get("driver_aligned")) else 0
    breadth = 1 if snap.get("sector_breadth_supportive") else 0
    # Amendment: broad sector/breadth now weighted >= cluster, not background color.
    cluster_or_breadth = max(cluster, breadth)  # 4

    catalyst = 1 if (snap.get("fresh_catalyst") and snap.get("catalyst_price_confirmed")) else 0  # 5

    rs_rw = snap.get("rs_rw_normalized") or 0.0  # 6
    # Sign it toward the forecast side rather than raw, so "strong but wrong way" doesn't rank up.
    rs_rw_aligned = rs_rw if stage1.state == "UP" else -rs_rw

    participation = metrics.participation_trend(snap.get("premarket_bars") or [], DEFAULT_THRESHOLDS)  # 7
    participation_score = {"accelerating": 1, "stable": 0, "decelerating": -1, "unavailable": 0}[participation]

    cross_market_extra = 0  # breadth already folded into #4; avoid double counting -- rule 47/32.
    # No separate signal beyond breadth in this input schema; placeholder for future data (factor 8).

    confidence_rank = {"HIGH": 2, "REDUCED": 1, "INSUFFICIENT": 0}[confidence.level]  # 9 tiebreaker

    # Sept-21 amendment: an already-extended, catalyst-less move should rank
    # *below* a flat/modest name with real breadth support. Folded into
    # quality (factor 2), not tacked on after the confidence tiebreaker,
    # so it actually has the weight the amendment intends rather than only
    # mattering once every other factor ties.
    extension_penalty = 0.0
    if stage1.extension == "EXTREME" and not catalyst:
        extension_penalty = -1.0
    breadth_bonus = 0.5 if (breadth and stage1.extension == "NORMAL") else 0.0

    # THE fix: this flag was being computed and reported but never actually
    # affected the ranking, so a ticker could be marked risky and still
    # rank #1. Confirmed predictive on real Sept 21 data (see
    # tests/test_premarket_ranking_real_case.py) -- apply it here.
    risk_penalty = thresholds.elevated_open_reversal_risk_penalty if elevated_risk else 0.0

    quality += extension_penalty + breadth_bonus + risk_penalty

    key = (
        clarity,
        quality,
        prior_regime,
        cluster_or_breadth,
        catalyst,
        rs_rw_aligned,
        participation_score,
        cross_market_extra,
        confidence_rank,
    )
    components = {
        "clarity": clarity,
        "quality": quality,
        "prior_regime": prior_regime,
        "cluster_or_breadth": cluster_or_breadth,
        "catalyst": catalyst,
        "rs_rw_aligned": rs_rw_aligned,
        "participation_score": participation_score,
        "confidence_rank": confidence_rank,
        "extension_penalty": extension_penalty,
        "breadth_bonus": breadth_bonus,
        "risk_penalty": risk_penalty,
    }
    return key, components


def build_row(snap: dict, thresholds: Thresholds = DEFAULT_THRESHOLDS) -> TickerRow:
    stage1 = classify_stage1(snap, thresholds)
    stage2 = classify_stage2(snap, stage1, thresholds)
    confidence = classify_confidence(snap, thresholds)
    side = side_from_route(stage1.state, stage2.route)
    g = grade(stage2, confidence)
    risk = elevated_open_reversal_risk(snap, stage1, thresholds)
    key, components = rank_key(snap, stage1, stage2, confidence, risk, thresholds)
    return TickerRow(
        ticker=snap["ticker"],
        stage1=stage1,
        stage2=stage2,
        confidence=confidence,
        side=side,
        grade=g,
        elevated_open_reversal_risk=risk,
        rank_key=key,
        rank_components=components,
    )


def rank_all(snapshots: list[dict], thresholds: Thresholds = DEFAULT_THRESHOLDS) -> list[TickerRow]:
    """Rule 4: all must be built (the 22/22 gate) before ranking. Rule 55/56:
    sort strictly by the rank_key, never by raw % move or headline drama."""
    if not snapshots:
        raise ValueError("no ticker snapshots supplied -- rule 4 (22/22 gate) cannot be satisfied")
    rows = [build_row(s, thresholds) for s in snapshots]
    rows.sort(key=lambda r: r.rank_key, reverse=True)
    return rows


def head_to_head_label(rows: list[TickerRow], thresholds: Thresholds = DEFAULT_THRESHOLDS) -> str:
    """Rules 59/60: CLEAR or NARROW separation between rank #1 and #2."""
    if len(rows) < 2:
        return "CLEAR"
    gap = rows[0].rank_key[0] - rows[1].rank_key[0]  # lead on the primary (clarity) axis
    return "CLEAR" if gap >= thresholds.head_to_head_clear_gap else "NARROW"


def ticker_of_the_day(rows: list[TickerRow]) -> Optional[TickerRow]:
    """Rule 61/62: strongest qualifying full-session forecast, or None."""
    for row in rows:
        if row.side != "MIXED" and row.grade != "MIXED" and row.confidence.level != "INSUFFICIENT":
            return row
    return None


def pick_executable_trade(
    ranked_rows: list[TickerRow],
    side: str,
    open_ts: str,
    regular_session_bars_by_ticker: dict[str, list[dict]],
) -> Optional[dict]:
    """THE actual fix: ranking (pre-open) and ORB execution (post-open)
    used to be two separate reports that were never reconciled, so a
    top-ranked pick with no real breakout could still be "the trade" by
    default. This walks the ranked CALL/PUT list in order and returns the
    first one that actually got a confirmed, sustained ORB breakout --
    skipping any that didn't, no matter how high they ranked before the
    open.

    Run this once bars are available past 9:45 ET. On Sept 21, 2026, fed
    the real rank order [HOOD, COIN, MSTR, AMD, ...] for CALL, this skips
    HOOD/COIN/MSTR (no confirmed breakout) and returns AMD -- the actual
    trade that should have been taken, automatically, instead of the
    premarket top pick that never confirmed.
    """
    candidates = [r for r in ranked_rows if r.side == side]
    for rank, row in enumerate(candidates, start=1):
        bars = regular_session_bars_by_ticker.get(row.ticker)
        if not bars:
            continue
        result = orb.compute_orb_and_breakout(bars, open_ts, side)
        if result.breakout_confirmed and result.sustained:
            return {"ticker": row.ticker, "premarket_rank": rank, "side": side, "orb": result}
    return None


def run_quality_gate(rows: list[TickerRow], expected_count: int) -> list[str]:
    """Rule 86 as an actual checklist, run before any report is emitted.

    Returns a list of violation strings; empty list means all gates passed.
    """
    violations = []
    if len(rows) != expected_count:
        violations.append(f"22/22 gate: got {len(rows)} rows, expected {expected_count} (rule 4)")
    for row in rows:
        if row.confidence.level == "INSUFFICIENT" and row.side != "MIXED":
            violations.append(f"{row.ticker}: INSUFFICIENT confidence but side={row.side}, expected MIXED")
        if row.stage1.state == "MIXED" and row.side != "MIXED":
            violations.append(f"{row.ticker}: Stage1 MIXED but side={row.side} (own-price-first violated)")
    return violations
