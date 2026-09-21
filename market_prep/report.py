"""Renders the required daily report format (rules 75-78) from computed
TickerRow objects. No narrative text is generated here -- structured
sections only, per the "no narrative/explanatory text" amendment.

Environment sections (Market Weather, VIX, Fear & Greed, Economic Calendar,
Overnight News, DXY, Treasury Yields, Sector Strength, Institutional
Confidence Refinements) are not computed by this engine -- they come from
web search / other sources per the rulebook's own data-source hierarchy,
and are passed in as plain strings to render.
"""

from __future__ import annotations

from . import engine


def _fmt_component(value) -> str:
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def render_ticker_table(rows: list[engine.TickerRow]) -> str:
    header = "| Rank | Ticker | Premarket State | Route | Side | Grade | Data Confidence |"
    sep = "|---|---|---|---|---|---|---|"
    lines = [header, sep]
    for i, row in enumerate(rows, start=1):
        lines.append(
            f"| {i} | {row.ticker} | {row.stage1.state} | {row.stage2.route} | "
            f"{row.side} | {row.grade} | {row.confidence.level} |"
        )
    return "\n".join(lines)


def top_n(rows: list[engine.TickerRow], side: str, n: int = 3) -> list[engine.TickerRow]:
    return [r for r in rows if r.side == side][:n]


def render_report(
    date_str: str,
    rows: list[engine.TickerRow],
    environment_sections: dict[str, str],
    violations: list[str],
) -> str:
    tod = engine.ticker_of_the_day(rows)
    h2h = engine.head_to_head_label(rows)
    calls = top_n(rows, "CALL", 3)
    puts = top_n(rows, "PUT", 3)
    avoid = [r for r in rows if r.side == "MIXED" or r.grade == "MIXED"]
    momentum = sorted((r for r in rows if r.side != "MIXED"), key=lambda r: r.rank_key, reverse=True)[:5]
    at_risk = [r for r in rows if r.elevated_open_reversal_risk]

    lines = []
    lines.append("Good morning. \U0001F60F")
    lines.append(f"NOIIR Options Market Prep -- {date_str}")
    lines.append("Prediction-of-record cutoff: ~9:00 AM ET")
    lines.append("")

    lines.append("## Environment")
    required_sections = [
        "Market Weather", "VIX", "Fear & Greed", "Economic Calendar", "Overnight News",
        "DXY", "Treasury Yields", "Sector Strength", "Institutional Confidence Refinements",
    ]
    for section in required_sections:
        lines.append(f"- {section}: {environment_sections.get(section, 'N/A')}")
    lines.append("")

    lines.append("## Full 22-Ticker Review")
    lines.append(render_ticker_table(rows))
    lines.append("")

    lines.append("## Top 3 Calls")
    lines.append(", ".join(r.ticker for r in calls) or "None qualify.")
    lines.append("## Next Best Calls")
    lines.append(", ".join(r.ticker for r in top_n(rows, "CALL", 6)[3:]) or "None.")
    lines.append("## Top 3 Puts")
    lines.append(", ".join(r.ticker for r in puts) or "None qualify.")
    lines.append("## Avoid Today")
    lines.append(", ".join(r.ticker for r in avoid) or "None.")
    lines.append("## Momentum Leaders")
    lines.append(" -> ".join(r.ticker for r in momentum) or "None.")
    lines.append("")

    lines.append("## Ticker of the Day")
    lines.append(f"{tod.ticker} -- {tod.side} -- {tod.grade}" if tod else "None -- No qualified opportunity.")
    lines.append("## Final Top-2 Head-to-Head")
    if len(rows) >= 2:
        lines.append(f"{rows[0].ticker} vs {rows[1].ticker}: {h2h} separation")
    lines.append("")

    if at_risk:
        lines.append("## Elevated Open-Reversal Risk (separate from Directional Grade)")
        lines.append(", ".join(r.ticker for r in at_risk))
        lines.append("")

    lines.append("## Overall Market Bias")
    up_count = sum(1 for r in rows if r.stage1.state == "UP")
    down_count = sum(1 for r in rows if r.stage1.state == "DOWN")
    bias = "UP" if up_count > down_count else "DOWN" if down_count > up_count else "MIXED"
    lines.append(f"{bias} -- Scorecard: UP {up_count} / DOWN {down_count} / MIXED {len(rows) - up_count - down_count}")
    lines.append("")

    lines.append("## Execution Reminder")
    lines.append(
        "Direction and execution are separate. No entry without a 15-min ORB "
        "break + close outside the range in the locked direction, plus valid ICC "
        "confirmation. ORB/ICC may veto this forecast; they never rewrite it."
    )
    lines.append("")

    lines.append("## Rule-86 Self-Check")
    if violations:
        lines.append("FAILED -- do not treat this as a valid Prediction of Record:")
        for v in violations:
            lines.append(f"- {v}")
    else:
        lines.append("PASSED -- 22/22 gate, cutoff discipline, and confidence/side consistency all held.")

    return "\n".join(lines)
