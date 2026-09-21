# trade-Journal

## market_prep

`market_prep/` is a deterministic engine for the NOIIR Options Market Prep
rulebook. It replaces the parts of the rulebook that were being judged by
an LLM in a chat (Stage 1/Stage 2 classification, the rule-55 ranking
hierarchy, data-confidence scoring, and the daily report/log) with real,
reproducible computation.

- `market_prep/schema.md` -- the input JSON a snapshot fetch step must produce.
- `python -m market_prep run --input snapshots.json --date YYYY-MM-DD` --
  classifies, ranks, renders the report, and appends the locked prediction
  to `market_prep_log.jsonl`.
- `python -m market_prep checkpoint --date ... --name 9:45ET --input outcomes.json` --
  records a later-checkpoint outcome against a logged prediction, without
  touching the locked fields.
- `tests/test_engine.py` -- run with `pytest`.

This module does not fetch market data itself; it consumes a snapshot JSON
produced wherever Webull/Alpha Vantage/news data is actually pulled (e.g. a
Claude session with those connectors). See `market_prep/schema.md` for the
exact contract, including what's still a deliberate human/LLM judgment call
(catalyst freshness, cluster/driver alignment) versus what's now computed.