"""Command-line entry point.

    python -m market_prep run --input snapshots.json --date 2026-09-22
    python -m market_prep checkpoint --date 2026-09-22 --name 9:45ET --input outcomes.json
    python -m market_prep orb-check --date 2026-09-22 --ticker MSTR --side CALL \
        --open-ts 2026-09-22T13:30:00+00:00 --bars mstr_bars.json

`snapshots.json` is a JSON object: {"environment": {...}, "tickers": [ ...snapshot dicts... ]}
See schema.md for the full snapshot field spec. This module does not fetch
any market data itself -- fetching (Webull/Alpha Vantage/web search) happens
wherever the snapshot JSON is produced; this only consumes it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import engine, report, store
from .thresholds import DEFAULT_THRESHOLDS


def cmd_run(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.input).read_text())
    snapshots = data["tickers"]
    environment = data.get("environment", {})

    rows = engine.rank_all(snapshots, DEFAULT_THRESHOLDS)
    violations = engine.run_quality_gate(rows, expected_count=len(snapshots))

    text = report.render_report(args.date, rows, environment, violations)
    print(text)

    if violations:
        print("\nQC GATE FAILED -- not logging as a Prediction of Record.", file=sys.stderr)
        return 1

    tod = engine.ticker_of_the_day(rows)
    store.log_prediction(args.date, rows, tod.ticker if tod else None)
    return 0


def cmd_checkpoint(args: argparse.Namespace) -> int:
    outcomes = json.loads(Path(args.input).read_text())
    store.record_checkpoint(args.date, args.name, outcomes)
    print(f"recorded checkpoint {args.name} for {args.date}")
    return 0


def cmd_orb_check(args: argparse.Namespace) -> int:
    bars = json.loads(Path(args.bars).read_text())
    result = store.record_orb_checkpoint(args.date, args.ticker, bars, args.open_ts, args.side)
    status = "SUSTAINED BREAKOUT" if result.sustained else ("BREAKOUT, NO FOLLOW-THROUGH" if result.breakout_confirmed else "NO VALID ENTRY")
    print(f"{args.ticker}: {status}")
    for r in result.reasons:
        print(f"  - {r}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="market_prep")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="classify, rank, render, and log today's prep")
    run_p.add_argument("--input", required=True, help="path to snapshots JSON")
    run_p.add_argument("--date", required=True, help="e.g. 2026-09-22")
    run_p.set_defaults(func=cmd_run)

    cp_p = sub.add_parser("checkpoint", help="record a later-checkpoint outcome for a logged date")
    cp_p.add_argument("--date", required=True)
    cp_p.add_argument("--name", required=True, help="e.g. 9:45ET")
    cp_p.add_argument("--input", required=True, help="path to outcomes JSON")
    cp_p.set_defaults(func=cmd_checkpoint)

    orb_p = sub.add_parser("orb-check", help="check whether a locked side got a valid, sustained ORB breakout")
    orb_p.add_argument("--date", required=True)
    orb_p.add_argument("--ticker", required=True)
    orb_p.add_argument("--side", required=True, choices=["CALL", "PUT"])
    orb_p.add_argument("--open-ts", required=True, help="9:30 AM ET regular-session open, ISO8601")
    orb_p.add_argument("--bars", required=True, help="path to regular-session bars JSON")
    orb_p.set_defaults(func=cmd_orb_check)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
