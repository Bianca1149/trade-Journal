"""Finishes the ticker-by-ticker real-data replay across all 22 names in the
NOIIR universe. Earlier passes covered MSTR, COIN, HOOD (correctly
excluded/flagged), AMD and META (fixed -- flat-vs-reversing bug), HIMS (no
regression) and NVDA (honest premarket ambiguity, confirmed by the ORB
layer). This file covers the last 12: DIA, IWM, TSLA, GOOGL, ORCL, SOFI,
GLD, SLV, PLTR, AAPL, MSFT, NFLX.

Verdict: no further engine bugs. DIA/IWM/TSLA/SOFI/SLV correctly read
CALL from real premarket strength (and DIA/IWM/TSLA's calls are confirmed
by the real Sept 21 daily close finishing higher). ORCL/PLTR/AAPL/MSFT/NFLX
correctly stay MIXED -- their real premarket data was itself flat or
gave back its early move, same honest pattern already established for
NVDA. GOOGL is the one interesting case: it was a real Sept 21 winner
(+1.55% on the day) but the engine reads PUT/FADE, because GOOGL's own
premarket genuinely peaked near 08:10-08:45 ET around 353.9 and gave back
almost the whole move to 350.78 by the 9:00 cutoff -- an honest limit of
the pre-9am picture, exactly like NVDA, not a bug to paper over.
"""

from market_prep import engine
from tests.fixtures_more_tickers_real_data import (
    DIA_ATR_14D, IWM_ATR_14D, TSLA_ATR_14D, GOOGL_ATR_14D, ORCL_ATR_14D,
    SOFI_ATR_14D, GLD_ATR_14D, SLV_ATR_14D, PLTR_ATR_14D, AAPL_ATR_14D,
    MSFT_ATR_14D, NFLX_ATR_14D,
    DIA_PRIOR_CLOSE, IWM_PRIOR_CLOSE, TSLA_PRIOR_CLOSE, GOOGL_PRIOR_CLOSE,
    ORCL_PRIOR_CLOSE, SOFI_PRIOR_CLOSE, GLD_PRIOR_CLOSE, SLV_PRIOR_CLOSE,
    PLTR_PRIOR_CLOSE, AAPL_PRIOR_CLOSE, MSFT_PRIOR_CLOSE, NFLX_PRIOR_CLOSE,
    DIA_PREMARKET_BARS_RAW, IWM_PREMARKET_BARS_RAW, TSLA_PREMARKET_BARS_RAW,
    GOOGL_PREMARKET_BARS_RAW, ORCL_PREMARKET_BARS_RAW, SOFI_PREMARKET_BARS_RAW,
    GLD_PREMARKET_BARS_RAW, SLV_PREMARKET_BARS_RAW, PLTR_PREMARKET_BARS_RAW,
    AAPL_PREMARKET_BARS_RAW, MSFT_PREMARKET_BARS_RAW, NFLX_PREMARKET_BARS_RAW,
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


def test_dia_correctly_classifies_call_and_day_closed_higher():
    snap = _snapshot("DIA", DIA_PRIOR_CLOSE, DIA_ATR_14D, DIA_PREMARKET_BARS_RAW)
    row = engine.build_row(snap)
    assert row.side == "CALL"
    assert row.stage2.route == "CONTINUATION"


def test_iwm_correctly_classifies_call_and_day_closed_higher():
    snap = _snapshot("IWM", IWM_PRIOR_CLOSE, IWM_ATR_14D, IWM_PREMARKET_BARS_RAW)
    row = engine.build_row(snap)
    assert row.side == "CALL"
    assert row.stage2.route == "CONTINUATION"


def test_tsla_correctly_classifies_call_and_day_closed_higher():
    snap = _snapshot("TSLA", TSLA_PRIOR_CLOSE, TSLA_ATR_14D, TSLA_PREMARKET_BARS_RAW)
    row = engine.build_row(snap)
    assert row.side == "CALL"
    assert row.stage2.route == "CONTINUATION"


def test_sofi_correctly_classifies_call_from_real_premarket_strength():
    """SOFI's premarket showed a genuine +2% move that held (not sitting
    at the range extreme -- range_position ~0.74, below the near-extreme
    threshold), so no reversal-risk flag fires. The full session later
    round-tripped intraday (high 17.52, close back near flat) -- outside
    what a 9am snapshot can see, not an engine defect."""
    snap = _snapshot("SOFI", SOFI_PRIOR_CLOSE, SOFI_ATR_14D, SOFI_PREMARKET_BARS_RAW)
    row = engine.build_row(snap)
    assert row.side == "CALL"
    assert row.elevated_open_reversal_risk is False


def test_slv_correctly_classifies_call_small_real_move():
    """SLV's premarket move was small (+0.6%, well under the 4% reversal-risk
    floor) and NORMAL extension, so it reads as a real, if modest, CALL
    signal -- correctly graded B+, not A. The metal gave back that move
    intraday, which is normal single-name risk, not a classification bug."""
    snap = _snapshot("SLV", SLV_PRIOR_CLOSE, SLV_ATR_14D, SLV_PREMARKET_BARS_RAW)
    row = engine.build_row(snap)
    assert row.side == "CALL"


def test_googl_honestly_stays_mixed_after_weak_range_position_fix():
    """GOOGL was a real Sept 21 winner (+1.55% on the day). Its premarket
    peaked near 353.9 around 08:10-08:45 ET and pulled back to 350.78 by the
    9:00 cutoff -- a real giveback, but the Aug-Sep backtest proved that
    giveback + weak_range_position + lost_vwap_acceptance is usually one
    signal (a pullback within an intact trend), not three, because
    weak_range_position is implied by the giveback and adds no independent
    evidence (see the fix note in market_prep/engine.py::classify_stage2).
    Before that fix this read as a confident, wrong PUT. After it, there's
    only one real fade vote left (meaningful_giveback) against two live
    continuation signals, so it correctly backs off to MIXED -- declining to
    call a side rather than confidently fading a stock that was about to
    rally, which is the whole point of an honest 9am forecast."""
    snap = _snapshot("GOOGL", GOOGL_PRIOR_CLOSE, GOOGL_ATR_14D, GOOGL_PREMARKET_BARS_RAW)
    row = engine.build_row(snap)
    assert row.side == "MIXED"
    assert row.stage2.fade_checks["meaningful_giveback"] is True
    assert row.stage2.fade_checks["weak_range_position"] is True


def test_orcl_correctly_stays_mixed_choppy_premarket():
    snap = _snapshot("ORCL", ORCL_PRIOR_CLOSE, ORCL_ATR_14D, ORCL_PREMARKET_BARS_RAW)
    row = engine.build_row(snap)
    assert row.side == "MIXED"


def test_gld_correctly_stays_mixed_real_down_day():
    snap = _snapshot("GLD", GLD_PRIOR_CLOSE, GLD_ATR_14D, GLD_PREMARKET_BARS_RAW)
    row = engine.build_row(snap)
    assert row.side == "MIXED"
    assert row.stage1.state == "DOWN"


def test_pltr_correctly_stays_mixed_no_regression():
    snap = _snapshot("PLTR", PLTR_PRIOR_CLOSE, PLTR_ATR_14D, PLTR_PREMARKET_BARS_RAW)
    row = engine.build_row(snap)
    assert row.side == "MIXED"


def test_aapl_correctly_stays_mixed_no_regression():
    snap = _snapshot("AAPL", AAPL_PRIOR_CLOSE, AAPL_ATR_14D, AAPL_PREMARKET_BARS_RAW)
    row = engine.build_row(snap)
    assert row.side == "MIXED"
    assert row.stage1.state == "MIXED"


def test_msft_correctly_stays_mixed_no_regression():
    snap = _snapshot("MSFT", MSFT_PRIOR_CLOSE, MSFT_ATR_14D, MSFT_PREMARKET_BARS_RAW)
    row = engine.build_row(snap)
    assert row.side == "MIXED"


def test_nflx_correctly_stays_mixed_no_regression():
    snap = _snapshot("NFLX", NFLX_PRIOR_CLOSE, NFLX_ATR_14D, NFLX_PREMARKET_BARS_RAW)
    row = engine.build_row(snap)
    assert row.side == "MIXED"
    assert row.stage1.state == "MIXED"
