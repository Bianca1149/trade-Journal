# Input snapshot schema

This engine does not fetch data itself. Whatever fetches data (a Claude
session with the Webull/Alpha Vantage connectors, or a script with your own
API keys) needs to produce a JSON file matching this shape and pass it to
`python -m market_prep run --input snapshots.json --date YYYY-MM-DD`.

```json
{
  "environment": {
    "Market Weather": "free text from web search / other sources",
    "VIX": "...",
    "Fear & Greed": "...",
    "Economic Calendar": "...",
    "Overnight News": "...",
    "DXY": "...",
    "Treasury Yields": "...",
    "Sector Strength": "...",
    "Institutional Confidence Refinements": "..."
  },
  "tickers": [
    {
      "ticker": "HOOD",
      "prior_close": 41.20,
      "premarket_bars": [
        {"ts": "2026-09-21T08:00:00-04:00", "open": 41.1, "high": 41.4, "low": 41.05, "close": 41.35, "volume": 12000}
      ],
      "last_price": 43.10,
      "last_price_ts": "2026-09-21T08:59:40-04:00",
      "fetched_at": "2026-09-21T08:59:45-04:00",
      "cutoff_ts": "2026-09-21T09:00:00-04:00",
      "atr_14d": 1.35,
      "secondary_last_price": 43.09,
      "data_missing": false,
      "fresh_catalyst": true,
      "catalyst_price_confirmed": true,
      "cluster_aligned": true,
      "driver_aligned": false,
      "sector_breadth_supportive": true,
      "prior_regime_aligned": true,
      "rs_rw_normalized": 0.42
    }
  ]
}
```

## Field notes

- `premarket_bars`: ideally 1-5 minute bars, prior session close through the
  cutoff. Empty/absent list + `data_missing: true` forces Data Confidence to
  INSUFFICIENT automatically, per the Sept-18 amendment -- don't backfill it
  with reasoning.
- `atr_14d`: prior 14-trading-day ATR (daily bars), own-instrument, not a
  benchmark's.
- `fresh_catalyst` / `catalyst_price_confirmed`: set by whoever reads the
  Alpha Vantage news-sentiment output (or other source) for that ticker.
  This is the one genuinely qualitative judgment call left in the pipeline
  (rules 35-38) -- everything downstream of it (ranking weight, side
  mapping) is deterministic once these booleans are set.
- `cluster_aligned` / `driver_aligned` / `sector_breadth_supportive`:
  booleans set from the cluster/driver checks (rules 32-34) and sector
  context (rule 47) -- again the interpretation happens once, upstream,
  not re-litigated inside the ranking.
- `prior_regime_aligned`: `true` if today's move confirms/extends the prior
  session regime, `false` if it's an unconfirmed reversal against it, `null`
  if not applicable/unresolved (rule 17).
- `rs_rw_normalized`: signed, ATR-normalized relative strength/weakness vs.
  an appropriate benchmark or peer (rule 44). Positive favors the ticker
  being relatively strong.
- `index_confirmation`: `true` if SPY/QQQ's own premarket state (UP/DOWN)
  agrees with this ticker's Stage 1 state, `false`/omitted otherwise. Set
  for every ticker except SPY/QQQ themselves. This was previously a
  hardcoded no-op in the ranking (rule 55 factor 8) -- wire it from real
  SPY/QQQ premarket data, since it was the single strongest signal on the
  Sept 21, 2026 session (SPY and QQQ both confirmed risk-on before the
  open) and it never reached the ranking.

## Alpha Vantage rate limit

The free tier is 25 requests/day, 5/minute. 22 tickers each needing a
catalyst check exceeds that on its own. Two practical options: (1) only
spend catalyst-check calls on tickers whose Stage 1 displacement clears
`min_move_atr_fraction` -- MIXED tickers don't need one, which usually cuts
the list well below 25; or (2) upgrade the tier. Whichever you pick, a
ticker with no catalyst check performed should get `fresh_catalyst: false`,
not a guess -- rule 10 (never fabricate optional data that can't be found).
