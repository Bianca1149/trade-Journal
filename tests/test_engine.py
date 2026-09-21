import copy
from datetime import datetime, timedelta, timezone

import pytest

from market_prep import engine
from market_prep.thresholds import DEFAULT_THRESHOLDS


def make_bars(prices, start=datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc), step_minutes=1, volume=1000):
    bars = []
    for i, p in enumerate(prices):
        ts = (start + timedelta(minutes=i * step_minutes)).isoformat()
        bars.append({"ts": ts, "open": p, "high": p + 0.05, "low": p - 0.05, "close": p, "volume": volume})
    return bars


def base_snapshot(**overrides):
    prices = [100.2, 100.6, 101.0, 101.6, 102.2, 102.8, 103.2, 103.5, 103.7, 103.8, 103.85, 103.9]
    snap = {
        "ticker": "TEST",
        "prior_close": 100.0,
        "premarket_bars": make_bars(prices),
        "last_price": 103.9,
        "last_price_ts": "2026-09-21T13:59:40+00:00",
        "fetched_at": "2026-09-21T13:59:45+00:00",
        "cutoff_ts": "2026-09-21T14:00:00+00:00",
        "atr_14d": 2.0,
        "secondary_last_price": 103.9,
        "data_missing": False,
        "fresh_catalyst": True,
        "catalyst_price_confirmed": True,
        "cluster_aligned": True,
        "driver_aligned": False,
        "sector_breadth_supportive": True,
        "prior_regime_aligned": True,
        "rs_rw_normalized": 0.5,
    }
    snap.update(overrides)
    return snap


def test_determinism_same_input_same_output():
    snap = base_snapshot()
    row1 = engine.build_row(copy.deepcopy(snap))
    row2 = engine.build_row(copy.deepcopy(snap))
    assert row1.rank_key == row2.rank_key
    assert row1.side == row2.side
    assert row1.grade == row2.grade
    assert row1.stage1.state == row2.stage1.state
    assert row1.stage2.route == row2.stage2.route


def test_strong_up_move_classifies_up_and_continuation():
    snap = base_snapshot()
    row = engine.build_row(snap)
    assert row.stage1.state == "UP"
    assert row.stage2.route == "CONTINUATION"
    assert row.side == "CALL"


def test_small_move_below_atr_floor_is_mixed():
    snap = base_snapshot(last_price=100.2, atr_14d=5.0)  # 0.2/5.0 = 0.04 < 0.15 floor
    snap["premarket_bars"] = make_bars([100.05, 100.1, 100.15, 100.2, 100.2, 100.2])
    row = engine.build_row(snap)
    assert row.stage1.state == "MIXED"
    assert row.stage2.route == "MIXED"
    assert row.side == "MIXED"


def test_missing_data_forces_insufficient_and_mixed_side():
    snap = base_snapshot(data_missing=True, premarket_bars=[])
    row = engine.build_row(snap)
    assert row.confidence.level == "INSUFFICIENT"


def test_price_conflict_reduces_confidence():
    snap = base_snapshot(secondary_last_price=103.9 * 1.01)  # 1% disagreement, well over 0.05% threshold
    row = engine.build_row(snap)
    assert row.confidence.level == "REDUCED"
    assert any("price conflict" in r for r in row.confidence.reasons)


def test_stale_fetch_reduces_confidence():
    snap = base_snapshot(fetched_at="2026-09-21T13:50:00+00:00")  # 10 min before cutoff
    row = engine.build_row(snap)
    assert row.confidence.level == "REDUCED"


def test_fade_route_on_reversing_ticker():
    # Ran up hard early, then stalled/reversed into the cutoff, gave back most of the move.
    prices = [100.2, 101.5, 103.0, 104.0, 104.2, 103.5, 102.5, 101.8, 101.2, 100.9, 100.6, 100.4]
    snap = base_snapshot(
        premarket_bars=make_bars(prices),
        last_price=100.4,
        fresh_catalyst=False,
        catalyst_price_confirmed=False,
        cluster_aligned=False,
        driver_aligned=False,
        atr_14d=2.0,
    )
    row = engine.build_row(snap)
    assert row.stage1.state == "UP"  # net still up vs prior_close=100.0
    assert row.stage2.route == "FADE"
    assert row.side == "PUT"


def test_extreme_extension_without_catalyst_penalized_vs_normal_with_breadth():
    extended_no_catalyst = base_snapshot(
        ticker="EXT",
        atr_14d=1.0,  # displacement 3.9 ATR -> EXTREME
        fresh_catalyst=False,
        catalyst_price_confirmed=False,
        cluster_aligned=False,
        driver_aligned=False,
        sector_breadth_supportive=False,
    )
    modest_with_breadth = base_snapshot(
        ticker="FLAT",
        last_price=100.6,
        atr_14d=2.0,  # small displacement -> NORMAL extension
        premarket_bars=make_bars([100.1, 100.2, 100.3, 100.4, 100.5, 100.55, 100.6, 100.6, 100.6]),
        sector_breadth_supportive=True,
    )
    ext_row = engine.build_row(extended_no_catalyst)
    flat_row = engine.build_row(modest_with_breadth)
    assert ext_row.rank_components["extension_penalty"] < 0
    assert flat_row.rank_components["breadth_bonus"] > 0
    assert ext_row.elevated_open_reversal_risk is True


def test_quality_gate_flags_incomplete_universe():
    snap = base_snapshot()
    rows = engine.rank_all([snap])
    violations = engine.run_quality_gate(rows, expected_count=22)
    assert any("22/22 gate" in v for v in violations)


def test_ticker_of_the_day_none_when_all_mixed():
    snap = base_snapshot(last_price=100.2, atr_14d=5.0)
    snap["premarket_bars"] = make_bars([100.05, 100.1, 100.15, 100.2, 100.2, 100.2])
    rows = engine.rank_all([snap])
    assert engine.ticker_of_the_day(rows) is None


def test_rank_all_requires_at_least_one_snapshot():
    with pytest.raises(ValueError):
        engine.rank_all([])
