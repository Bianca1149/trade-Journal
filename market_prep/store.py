"""Daily log of locked predictions and later scoring against real outcomes.

Rule 82 admitted this never existed ("no tracking log actually implemented
-- user is tracking manually"). Without it, rule 84's "no framework change
without a repeated, evidence-backed failure pattern" is unenforceable --
you can't see a repeated pattern you never recorded. This is a flat
JSON-lines file: one line per locked prediction, appended to later with
checkpoint outcomes.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import engine

DEFAULT_LOG_PATH = Path(__file__).resolve().parent.parent / "market_prep_log.jsonl"


def log_prediction(date_str: str, rows: list[engine.TickerRow], tod_ticker: str | None, log_path: Path = DEFAULT_LOG_PATH) -> None:
    """Append the locked Prediction of Record (rule 64). Never rewritten after this."""
    entry = {
        "date": date_str,
        "ticker_of_the_day": tod_ticker,
        "rows": [
            {
                "ticker": r.ticker,
                "stage1_state": r.stage1.state,
                "route": r.stage2.route,
                "side": r.side,
                "grade": r.grade,
                "confidence": r.confidence.level,
                "elevated_open_reversal_risk": r.elevated_open_reversal_risk,
            }
            for r in rows
        ],
        "checkpoints": {},  # filled in later by record_checkpoint()
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def record_checkpoint(date_str: str, checkpoint_name: str, outcomes: dict, log_path: Path = DEFAULT_LOG_PATH) -> None:
    """Fill in a later checkpoint (rule 81: 9:45/10:30/12:00/close) without
    touching the locked Prediction of Record fields themselves (rule 6/64)."""
    if not log_path.exists():
        raise FileNotFoundError(f"no log at {log_path} -- nothing to checkpoint")
    lines = log_path.read_text().splitlines()
    updated = []
    found = False
    for line in lines:
        entry = json.loads(line)
        if entry["date"] == date_str:
            entry["checkpoints"][checkpoint_name] = outcomes
            found = True
        updated.append(json.dumps(entry))
    if not found:
        raise ValueError(f"no logged prediction for {date_str}")
    log_path.write_text("\n".join(updated) + "\n")


def load_log(log_path: Path = DEFAULT_LOG_PATH) -> list[dict]:
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
