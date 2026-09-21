"""Real case, Sept 21, 2026: HOOD/MSTR/COIN were the three CALL picks, all
labeled Ticker of the Day / Top Calls. AMD, NVDA, META, QQQ, AMZN, SPY were
the tickers that actually kept climbing through the day.

This checks MSTR and COIN (both real regular-session data) against AMD: did
each one break its own 9:30-9:45 opening range and keep going, or did the
day's whole move happen inside that first 15 minutes with nothing after?
"""

from market_prep.orb import compute_orb_and_breakout
from tests.fixtures_orb_real_data import MSTR_BARS_RAW, COIN_BARS_RAW, AMD_BARS_RAW, NVDA_BARS_RAW, to_dicts

OPEN_TS = "2026-09-21T13:30:00+00:00"  # 9:30 AM ET


def test_mstr_never_broke_its_opening_range():
    result = compute_orb_and_breakout(to_dicts(MSTR_BARS_RAW), OPEN_TS, "CALL")
    assert result.breakout_confirmed is False
    assert result.orb_high == 169.5  # set in the first 15 minutes, 9:30-9:45
    # the day's actual high after 9:45 (169.1499) never reached back to it
    after_orb_high = max(b["high"] for b in to_dicts(MSTR_BARS_RAW) if b["ts"] > "2026-09-21T13:45:00+00:00")
    assert after_orb_high < result.orb_high


def test_coin_never_broke_its_opening_range():
    result = compute_orb_and_breakout(to_dicts(COIN_BARS_RAW), OPEN_TS, "CALL")
    assert result.breakout_confirmed is False
    assert result.orb_high == 208.33
    after_orb_high = max(b["high"] for b in to_dicts(COIN_BARS_RAW) if b["ts"] > "2026-09-21T13:45:00+00:00")
    assert after_orb_high < result.orb_high


def test_amd_broke_its_opening_range_and_kept_going():
    result = compute_orb_and_breakout(to_dicts(AMD_BARS_RAW), OPEN_TS, "CALL")
    assert result.breakout_confirmed is True
    assert result.sustained is True
    # AMD ran well beyond its breakout point through the close, not just a
    # one-bar poke back inside the range.
    assert result.max_follow_through > 5.0


def test_nvda_broke_its_opening_range_and_kept_going():
    """NVDA's premarket data was genuinely ambiguous (peaked early, faded
    into the 9:00 cutoff -- see test_full_replay_additional_tickers.py),
    but it broke its opening range almost immediately after 9:45 and ran
    all day. Exactly the case the ORB+ICC execution layer exists for:
    a real win the premarket forecast alone couldn't have been sure of."""
    result = compute_orb_and_breakout(to_dicts(NVDA_BARS_RAW), OPEN_TS, "CALL")
    assert result.breakout_confirmed is True
    assert result.sustained is True


def test_mstr_and_coin_would_have_produced_no_valid_entry():
    """Rule 70: entry requires a break AND a close outside the ORB in the
    locked direction. Neither MSTR nor COIN ever produced that close, so a
    CALL "trade" on either was never a valid ORB+ICC entry in the first
    place -- the loss traces to skipping the execution filter, not to the
    direction call itself (both ended the day green)."""
    for raw in (MSTR_BARS_RAW, COIN_BARS_RAW):
        result = compute_orb_and_breakout(to_dicts(raw), OPEN_TS, "CALL")
        assert result.breakout_confirmed is False
