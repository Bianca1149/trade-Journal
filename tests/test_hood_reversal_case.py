"""Real case: HOOD, September 21, 2026.

The chat-based prep called HOOD Ticker of the Day, CALL, grade A-, Data
Confidence High. Real data pulled after the fact (Webull) shows HOOD
topped out premarket around $126.75, then round-tripped straight down to
about $121.50 in the first 45 minutes after the 9:30 open -- exactly the
"looked great before the bell, reversed at the open" pattern rule 55's
Sept-21 amendment exists to flag.

This test uses only the real premarket bars up through the ~9:00 AM ET
cutoff (13:00 UTC) -- nothing after the open -- to prove the engine flags
this as elevated_open_reversal_risk *before* the open, not after.
"""

from market_prep import engine

# Real HOOD daily bars, 2026-08-28 through 2026-09-18 (the 14 trading days
# before Sept 21), pulled via Webull. Used to compute a real 14d ATR
# instead of guessing one.
_DAILY_BARS = [
    {"high": 110.500000, "low": 104.150000, "close": 104.260000},  # 08-28
    {"high": 105.470000, "low": 100.680000, "close": 104.810000},  # 08-31
    {"high": 106.96, "low": 102.45, "close": 103.51},              # 09-01
    {"high": 107.46, "low": 101.89, "close": 106.99},              # 09-02
    {"high": 124.88, "low": 113.04, "close": 124.72},              # 09-03
    {"high": 124.70, "low": 119.82, "close": 122.11},              # 09-04
    {"high": 125.25, "low": 117.08, "close": 117.34},              # 09-08
    {"high": 121.42, "low": 115.09, "close": 115.28},              # 09-09
    {"high": 116.30, "low": 111.95, "close": 113.33},              # 09-10
    {"high": 116.40, "low": 111.02, "close": 112.57},              # 09-11
    {"high": 116.345, "low": 111.960, "close": 114.33},            # 09-14
    {"high": 112.850, "low": 105.8593, "close": 110.45},           # 09-15
    {"high": 111.05, "low": 101.7045, "close": 104.42},            # 09-16
    {"high": 110.55, "low": 106.08, "close": 109.81},              # 09-17
    {"high": 120.5699, "low": 111.06, "close": 119.82},            # 09-18
]


def _atr_14d(daily_bars):
    trs = []
    for i in range(1, len(daily_bars)):
        bar, prev_close = daily_bars[i], daily_bars[i - 1]["close"]
        trs.append(max(bar["high"] - bar["low"], abs(bar["high"] - prev_close), abs(bar["low"] - prev_close)))
    return sum(trs) / len(trs)


# Real HOOD premarket bars, 2026-09-21, 07:40-09:00 AM ET (11:40-13:00 UTC)
# -- everything available by the ~9:00 AM ET cutoff, nothing after.
_PREMARKET_BARS = [
    {"ts": "2026-09-21T11:40:00+00:00", "open": 125.52, "high": 125.6, "low": 125.3, "close": 125.4521, "volume": 7957},
    {"ts": "2026-09-21T11:45:00+00:00", "open": 125.47, "high": 126.2, "low": 125.35, "close": 126.185, "volume": 33202},
    {"ts": "2026-09-21T11:50:00+00:00", "open": 126.12, "high": 126.64, "low": 126.04, "close": 126.3, "volume": 35487},
    {"ts": "2026-09-21T11:55:00+00:00", "open": 126.31, "high": 126.4, "low": 126.0, "close": 126.1, "volume": 19638},
    {"ts": "2026-09-21T12:00:00+00:00", "open": 126.06, "high": 126.22, "low": 125.6482, "close": 126.08, "volume": 18316},
    {"ts": "2026-09-21T12:05:00+00:00", "open": 126.05, "high": 126.5, "low": 125.9925, "close": 126.074, "volume": 19412},
    {"ts": "2026-09-21T12:10:00+00:00", "open": 126.1, "high": 126.25, "low": 125.63, "close": 125.83, "volume": 14276},
    {"ts": "2026-09-21T12:15:00+00:00", "open": 125.6356, "high": 126.3, "low": 125.63, "close": 126.3, "volume": 10256},
    {"ts": "2026-09-21T12:20:00+00:00", "open": 126.17, "high": 126.44, "low": 125.6, "close": 125.8, "volume": 15701},
    {"ts": "2026-09-21T12:25:00+00:00", "open": 125.8, "high": 126.0, "low": 125.6003, "close": 125.7872, "volume": 20238},
    {"ts": "2026-09-21T12:30:00+00:00", "open": 125.7872, "high": 126.2, "low": 125.65, "close": 126.07, "volume": 9102},
    {"ts": "2026-09-21T12:35:00+00:00", "open": 126.15, "high": 126.3, "low": 126.0, "close": 126.18, "volume": 9194},
    {"ts": "2026-09-21T12:40:00+00:00", "open": 126.1, "high": 126.45, "low": 126.02, "close": 126.3097, "volume": 7900},
    {"ts": "2026-09-21T12:45:00+00:00", "open": 126.09, "high": 126.3, "low": 126.08, "close": 126.19, "volume": 6885},
    {"ts": "2026-09-21T12:50:00+00:00", "open": 126.25, "high": 126.55, "low": 126.12, "close": 126.3745, "volume": 13268},
    {"ts": "2026-09-21T12:55:00+00:00", "open": 126.49, "high": 126.55, "low": 126.18, "close": 126.23, "volume": 6540},
    {"ts": "2026-09-21T13:00:00+00:00", "open": 126.4445, "high": 126.7499, "low": 126.0, "close": 126.56, "volume": 18161},
]

# What actually happened right after -- for the checkpoint step only, never
# fed into the pre-open classification above (rule 6: no-hindsight rule).
_ACTUAL_945_ET_PRICE = 121.74  # from the 13:50 UTC bar, ~9:50 AM ET
_ACTUAL_OPEN_PRICE = 125.00
_ACTUAL_OPEN_HIGH = 126.41


def hood_snapshot():
    return {
        "ticker": "HOOD",
        "prior_close": 119.82,  # 09-18 close
        "premarket_bars": _PREMARKET_BARS,
        "last_price": 126.56,
        "last_price_ts": "2026-09-21T13:00:00+00:00",
        "fetched_at": "2026-09-21T13:00:05+00:00",
        "cutoff_ts": "2026-09-21T13:00:00+00:00",  # 9:00 AM ET
        "atr_14d": _atr_14d(_DAILY_BARS),
        "secondary_last_price": None,
        "data_missing": False,
        # No confirmed, price-anchored catalyst was cited for HOOD in the
        # real report -- just a ranking result. So this is False, per rule
        # 10 (never fabricate optional data that can't be found).
        "fresh_catalyst": False,
        "catalyst_price_confirmed": False,
        "cluster_aligned": False,
        "driver_aligned": False,
        "sector_breadth_supportive": False,
        "prior_regime_aligned": None,
        "rs_rw_normalized": None,
    }


def test_real_hood_atr_is_computed_not_guessed():
    atr = _atr_14d(_DAILY_BARS)
    assert 6.5 < atr < 8.0  # ~7.21 from real daily bars


def test_hood_stage1_was_a_real_but_atr_normal_move():
    row = engine.build_row(hood_snapshot())
    assert row.stage1.state == "UP"
    # This is the crux of why the old ATR-only check missed it: HOOD's own
    # ATR is already so elevated (~7.2, after a volatile two weeks) that a
    # genuine +5.6% premarket move only reads as NORMAL extension.
    assert row.stage1.extension == "NORMAL"


def test_hood_flagged_elevated_open_reversal_risk_before_the_open():
    row = engine.build_row(hood_snapshot())
    assert row.elevated_open_reversal_risk is True, (
        "engine should have flagged HOOD as open-reversal risk using only "
        "data available by the 9:00 AM cutoff -- it round-tripped from the "
        "premarket high within 45 minutes of the open"
    )


def test_hood_real_outcome_confirms_the_flag_was_right():
    # Not part of the forecast -- this is the later checkpoint check
    # (rule 81), done only after the prediction was already locked above.
    premarket_high = max(b["high"] for b in _PREMARKET_BARS)
    assert _ACTUAL_945_ET_PRICE < premarket_high * 0.97, (
        "HOOD gave back more than 3% of its premarket high within the "
        "first ~20 minutes of the open -- the flagged risk materialized"
    )
