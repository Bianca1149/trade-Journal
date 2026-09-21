"""Continuing the full-22 replay after the pause-vs-reversal and
index-confirmation fixes: check more of the real winners/losers using
only real premarket data, to catch anything the AMD case alone didn't
cover.
"""

from market_prep import engine
from tests.fixtures_additional_premarket_real_data import (
    META_ATR_14D, NVDA_ATR_14D, HIMS_ATR_14D,
    META_PRIOR_CLOSE, NVDA_PRIOR_CLOSE, HIMS_PRIOR_CLOSE,
    META_PREMARKET_BARS_RAW, NVDA_PREMARKET_BARS_RAW, HIMS_PREMARKET_BARS_RAW,
    to_dicts,
)

CUTOFF_TS = "2026-09-21T13:00:00+00:00"


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
        "fresh_catalyst": False,
        "catalyst_price_confirmed": False,
        "cluster_aligned": False,
        "driver_aligned": False,
        "sector_breadth_supportive": False,
        "prior_regime_aligned": None,
        "rs_rw_normalized": None,
        # SPY/QQQ both confirmed UP premarket on the real Sept 21 session.
        "index_confirmation": True,
    }


def test_meta_correctly_classifies_call_using_only_premarket_data():
    """META was misclassified MIXED on the real day and was one of the
    biggest winners (broke ORB, ran +11%). With real premarket data and
    the flat-vs-reversing fix, it correctly classifies CALL."""
    snap = _snapshot("META", META_PRIOR_CLOSE, META_ATR_14D, META_PREMARKET_BARS_RAW)
    row = engine.build_row(snap)
    assert row.side == "CALL"
    assert row.stage2.route == "CONTINUATION"


def test_hims_still_correctly_classifies_call_no_regression():
    """HIMS was already correctly CALL in the real report and was a real
    winner. Confirms the fixes didn't regress an already-correct case."""
    snap = _snapshot("HIMS", HIMS_PRIOR_CLOSE, HIMS_ATR_14D, HIMS_PREMARKET_BARS_RAW)
    row = engine.build_row(snap)
    assert row.side == "CALL"
    assert row.stage2.route == "CONTINUATION"


def test_nvda_honestly_stays_mixed_premarket_ambiguity_is_real():
    """NVDA also won post-open, but its real premarket data shows it
    peaked around 9:50-10:00 AM ET then genuinely faded (gave back
    real retention, not just noise) into the 9:00 cutoff -- weak_range_position
    and lost_vwap_acceptance both fire. This is not a bug to paper over:
    the premarket picture itself was ambiguous, and NVDA's win was
    confirmed by the ORB breakout that happens after 9:30
    (test_orb_real_cases.py::test_nvda_broke_its_opening_range_and_kept_going),
    which is exactly the layer the rulebook assigns that job to
    (rules 68-72) -- not something the pre-9AM ranking should be forced
    to guess."""
    snap = _snapshot("NVDA", NVDA_PRIOR_CLOSE, NVDA_ATR_14D, NVDA_PREMARKET_BARS_RAW)
    row = engine.build_row(snap)
    assert row.side == "MIXED"
    assert row.stage2.fade_checks["weak_range_position"] is True
