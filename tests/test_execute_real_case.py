"""The actual fix: reconcile the premarket ranking with the real post-open
ORB result into ONE answer -- what to actually trade -- instead of two
separate reports the reader has to cross-check by hand.

Real Sept 21, 2026 case: the report ranked CALL candidates 1) HOOD 2) COIN
3) MSTR 4) AMD (rank order taken directly from the report you pasted).
HOOD/COIN/MSTR never got a confirmed ORB breakout (see
test_orb_real_cases.py); AMD did, and ran all day. pick_executable_trade
must walk right past the top three and land on AMD.
"""

from market_prep import engine
from tests.test_engine import base_snapshot
from tests.fixtures_orb_real_data import MSTR_BARS_RAW, COIN_BARS_RAW, AMD_BARS_RAW, to_dicts

OPEN_TS = "2026-09-21T13:30:00+00:00"


def _call_row(ticker: str) -> engine.TickerRow:
    # Only used to get a TickerRow with side="CALL" in the right rank slot --
    # the actual premarket classification for each of these is already
    # covered by test_engine.py and test_hood_reversal_case.py; this test is
    # about the ranking-vs-ORB reconciliation, not re-deriving Stage 1/2.
    return engine.build_row(base_snapshot(ticker=ticker))


def test_execution_skips_unconfirmed_top_picks_and_lands_on_amd():
    ranked = [_call_row(t) for t in ["HOOD", "COIN", "MSTR", "AMD"]]
    bars_by_ticker = {
        "COIN": to_dicts(COIN_BARS_RAW),
        "MSTR": to_dicts(MSTR_BARS_RAW),
        "AMD": to_dicts(AMD_BARS_RAW),
        # HOOD intentionally omitted -- no regular-session bars fetched for
        # it in this session; the function must skip missing data too,
        # not just failed breakouts.
    }
    trade = engine.pick_executable_trade(ranked, "CALL", OPEN_TS, bars_by_ticker)
    assert trade is not None
    assert trade["ticker"] == "AMD"
    assert trade["premarket_rank"] == 4
    assert trade["orb"].sustained is True


def test_execution_returns_none_if_nothing_confirms():
    ranked = [_call_row(t) for t in ["COIN", "MSTR"]]
    bars_by_ticker = {"COIN": to_dicts(COIN_BARS_RAW), "MSTR": to_dicts(MSTR_BARS_RAW)}
    trade = engine.pick_executable_trade(ranked, "CALL", OPEN_TS, bars_by_ticker)
    assert trade is None
