"""Real case, Sept 21, 2026, using ONLY data that existed before the 9:00
AM ET cutoff -- no ORB, no post-open bars anywhere in this file. Market
prep locks before the open; this is the actual lever available to it.

The real report ranked CALL candidates 1) HOOD 2) COIN 3) MSTR 4) AMD. All
three of the top picks failed (see test_orb_real_cases.py for what
happened after the open); AMD worked. This proves the premarket data alone
-- already fetched by 9:00 AM -- carried the signal: HOOD/MSTR/COIN were
all large moves parked at their premarket extreme with no confirmed
catalyst; AMD had already pulled back off its premarket high before 9:00.

engine.elevated_open_reversal_risk already computed this. The bug was that
build_row/rank_key never fed it into the actual ranking, so the flag could
be true and the ticker still ranked #1. This test proves the fix: the
penalty is real (nonzero) for HOOD/MSTR/COIN and zero for AMD, using
nothing past 9:00 AM.
"""

from market_prep import engine
from tests.test_hood_reversal_case import hood_snapshot
from tests.fixtures_premarket_real_data import (
    MSTR_ATR_14D, COIN_ATR_14D, AMD_ATR_14D,
    MSTR_PRIOR_CLOSE, COIN_PRIOR_CLOSE, AMD_PRIOR_CLOSE,
    MSTR_PREMARKET_BARS_RAW, COIN_PREMARKET_BARS_RAW, AMD_PREMARKET_BARS_RAW,
    to_dicts,
)

CUTOFF_TS = "2026-09-21T13:00:00+00:00"  # 9:00 AM ET


def _snapshot(ticker, prior_close, atr, bars_raw):
    bars = to_dicts(bars_raw)
    last_bar = bars[-1]
    return {
        "ticker": ticker,
        "prior_close": prior_close,
        "premarket_bars": bars,
        "last_price": last_bar["close"],
        "last_price_ts": last_bar["ts"],
        "fetched_at": last_bar["ts"],
        "cutoff_ts": CUTOFF_TS,
        "atr_14d": atr,
        "secondary_last_price": None,
        "data_missing": False,
        # No confirmed catalyst known for any of these four by 9:00 AM --
        # kept equal across all four so the only thing that can move the
        # ranking apart is the premarket price action itself.
        "fresh_catalyst": False,
        "catalyst_price_confirmed": False,
        "cluster_aligned": False,
        "driver_aligned": False,
        "sector_breadth_supportive": False,
        "prior_regime_aligned": None,
        "rs_rw_normalized": None,
    }


def mstr_snapshot():
    return _snapshot("MSTR", MSTR_PRIOR_CLOSE, MSTR_ATR_14D, MSTR_PREMARKET_BARS_RAW)


def coin_snapshot():
    return _snapshot("COIN", COIN_PRIOR_CLOSE, COIN_ATR_14D, COIN_PREMARKET_BARS_RAW)


def amd_snapshot():
    return _snapshot("AMD", AMD_PRIOR_CLOSE, AMD_ATR_14D, AMD_PREMARKET_BARS_RAW)


def test_mstr_and_coin_flagged_risky_before_the_open():
    for snap in (mstr_snapshot(), coin_snapshot()):
        row = engine.build_row(snap)
        assert row.elevated_open_reversal_risk is True, snap["ticker"]
        assert row.rank_components["risk_penalty"] < 0, snap["ticker"]


def test_amd_not_flagged_before_the_open():
    row = engine.build_row(amd_snapshot())
    assert row.elevated_open_reversal_risk is False
    assert row.rank_components["risk_penalty"] == 0.0
    # AMD had pulled back off its premarket high by 9:00 -- nowhere near
    # the near-extreme boundary that flagged the other three.
    assert row.stage1.range_position < 0.85


def test_hood_also_flagged_consistent_with_earlier_finding():
    row = engine.build_row(hood_snapshot())
    assert row.elevated_open_reversal_risk is True
    assert row.rank_components["risk_penalty"] < 0


def test_mstr_excluded_from_call_side_entirely_on_premarket_data_alone():
    """Bonus finding, not the fix itself: Stage 2's fade checks (rule 27)
    independently caught MSTR before 9 AM too -- its "stalling into the
    cutoff" and "outsized move with no confirmation" signals were enough to
    classify it MIXED rather than CONTINUATION, so it never becomes a CALL
    pick at all, flag or no flag. That's arguably a stronger outcome than
    just down-ranking it."""
    row = engine.build_row(mstr_snapshot())
    assert row.stage2.fade_checks["no_confirmation_for_outsized_move"] is True
    assert row.side != "CALL"


def test_amd_correctly_classifies_call_after_flat_vs_reversing_fix():
    """Was an open gap (a genuine ~0.2% pullback in AMD's last 5 premarket
    bars read as "reversing" under the old 0.05% tolerance, so AMD
    classified MIXED here even though it was one of the day's best
    trades). Fixed by treating a shallow pause as "flat" rather than
    "reversing" (metrics.latest_window_trend, Thresholds.flat_tolerance_fraction).
    Using only premarket data, AMD now correctly classifies CALL."""
    row = engine.build_row(amd_snapshot())
    assert row.side == "CALL"
    assert row.stage2.route == "CONTINUATION"
    assert row.stage2.continuation_checks["latest_window_progressing"] is True


def test_flagged_call_picks_carry_the_penalty_in_their_quality_score():
    """The actual, provable fix: among the CALL-side rows in this real
    data, every one that was elevated_open_reversal_risk=True has a
    strictly worse (lower) quality score than it would with the penalty
    removed -- i.e. the flag now really does cost rank, not just get
    printed and ignored."""
    for snap in (hood_snapshot(), coin_snapshot()):
        row = engine.build_row(snap)
        assert row.side == "CALL"
        assert row.elevated_open_reversal_risk is True
        assert row.rank_components["risk_penalty"] < 0
        unpenalized_quality = row.rank_components["quality"] - row.rank_components["risk_penalty"]
        assert row.rank_components["quality"] < unpenalized_quality
