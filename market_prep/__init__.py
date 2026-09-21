"""Deterministic engine for the NOIIR Options Market Prep rulebook.

This package replaces the parts of the rulebook that were being done by an
LLM "eyeballing" price data in a chat (Stage 1/Stage 2 classification,
the rule-55 ranking hierarchy, data-confidence scoring, and the daily
report/log) with actual, reproducible computation.

What stays outside this package on purpose: reading news for catalyst
freshness/price-confirmation, and judging cluster/driver alignment. Those
are genuinely qualitative and are supplied as explicit boolean/enum fields
on each TickerSnapshot rather than being computed here.
"""

from .thresholds import Thresholds, DEFAULT_THRESHOLDS

__all__ = ["Thresholds", "DEFAULT_THRESHOLDS"]
