"""Eligible stock-option evidence, built before any model sees it."""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from tradingagents.dataflows.router import route_to_vendor
from tradingagents.dataflows.symbols import normalize_symbol

logger = logging.getLogger(__name__)

METHOD = "get_option_chain"

UNAVAILABLE_NOTICE_TEMPLATE = (
    "Options data unavailable for {ticker} as of {trade_date}. No eligible "
    "option-chain observations were available for this instrument on that date. "
    "This report contains no options evidence and no inferred options signal."
)


@dataclass(frozen=True)
class OptionsEvidence:
    ticker: str
    trade_date: str
    observations: tuple[Mapping[str, Any], ...]
    rejected: int = 0
    reasons: tuple[str, ...] = ()
    provider_note: str = ""

    @property
    def usable(self) -> bool:
        return bool(self.observations)


def unavailable_options_notice(ticker: str, trade_date: str) -> str:
    return UNAVAILABLE_NOTICE_TEMPLATE.format(ticker=ticker, trade_date=trade_date)


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _availability_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            return None
        return value.astimezone(UTC).date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        pass
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(UTC).date()


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def _has_quote(row: Mapping[str, Any]) -> bool:
    return any(row.get(key) is not None for key in (
        "bid", "ask", "last", "implied_volatility", "open_interest", "volume",
    ))


def _normalise_record(
    record: Mapping[str, Any], requested: str, cutoff: date
) -> tuple[dict[str, Any] | None, str]:
    underlying = record.get("underlying")
    try:
        identity = normalize_symbol(str(underlying or ""))
    except Exception:
        identity = ""
    if identity != requested:
        return None, "identity"

    available = _availability_date(record.get("snapshot_at"))
    if available is None or available > cutoff:
        return None, "availability"

    expiry = _parse_date(record.get("expiry"))
    if expiry is None or expiry < cutoff:
        return None, "expiry"

    option_type = str(record.get("option_type") or "").strip().lower()
    if option_type not in {"call", "put"}:
        return None, "contract"

    strike = _number(record.get("strike"))
    if strike is None:
        return None, "contract"

    row = {
        **record,
        "underlying": requested,
        "expiry": expiry.isoformat(),
        "option_type": option_type,
        "strike": strike,
        "bid": _number(record.get("bid")),
        "ask": _number(record.get("ask")),
        "last": _number(record.get("last")),
        "volume": _number(record.get("volume")),
        "open_interest": _number(record.get("open_interest")),
        "implied_volatility": _number(record.get("implied_volatility")),
        "underlying_price": _number(record.get("underlying_price")),
    }
    if not _has_quote(row):
        return None, "quote"
    return row, ""


def eligible_observations(
    ticker: str, trade_date: str, records: list[Mapping[str, Any]]
) -> tuple[tuple[Mapping[str, Any], ...], int, tuple[str, ...]]:
    requested = normalize_symbol(ticker)
    cutoff = _parse_date(trade_date)
    if cutoff is None:
        return (), len(records), ("date",)

    chosen: dict[tuple[str, float, str], tuple[date, Mapping[str, Any]]] = {}
    rejected = 0
    reasons: list[str] = []
    for record in records:
        if not isinstance(record, Mapping):
            rejected += 1
            reasons.append("record")
            continue
        row, reason = _normalise_record(record, requested, cutoff)
        if row is None:
            rejected += 1
            reasons.append(reason)
            continue
        available = _availability_date(row.get("snapshot_at"))
        if available is None:
            rejected += 1
            reasons.append("availability")
            continue
        key = (str(row["expiry"]), float(row["strike"]), str(row["option_type"]))
        previous = chosen.get(key)
        if previous is not None and previous[0] >= available:
            rejected += 1
            reasons.append("duplicate")
            continue
        if previous is not None:
            rejected += 1
            reasons.append("duplicate")
        chosen[key] = (available, row)

    ordered = tuple(row for _available, row in sorted(
        chosen.values(), key=lambda item: (item[1]["expiry"], item[1]["strike"], item[1]["option_type"])
    ))
    return ordered, rejected, tuple(reasons)


def load_eligible_option_chain(ticker: str, trade_date: str) -> OptionsEvidence:
    try:
        records = route_to_vendor(METHOD, ticker, trade_date)
    except Exception as exc:
        logger.warning("Options provider failed for %s on %s: %s", ticker, trade_date, exc)
        return OptionsEvidence(ticker, trade_date, (), provider_note=type(exc).__name__)

    if not isinstance(records, (list, tuple)):
        note = str(records)[:200]
        logger.warning("Options provider returned no observation list for %s on %s: %s",
                       ticker, trade_date, note)
        return OptionsEvidence(ticker, trade_date, (), provider_note=note)

    observations, rejected, reasons = eligible_observations(ticker, trade_date, list(records))
    return OptionsEvidence(
        ticker, trade_date, observations, rejected, reasons,
        "empty" if not records else "",
    )


def _fmt(value: float | None, digits: int = 2) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def _atm_strike(rows: list[Mapping[str, Any]], price: float | None) -> float | None:
    if price is not None:
        return min((float(row["strike"]) for row in rows), key=lambda strike: abs(strike - price), default=None)

    calls = [row for row in rows if row["option_type"] == "call" and row.get("in_the_money") is not None]
    puts = [row for row in rows if row["option_type"] == "put" and row.get("in_the_money") is not None]
    estimates = []
    if calls:
        below = [float(row["strike"]) for row in calls if row["in_the_money"]]
        above = [float(row["strike"]) for row in calls if not row["in_the_money"]]
        if below and above:
            estimates.append((max(below) + min(above)) / 2)
    if puts:
        above = [float(row["strike"]) for row in puts if row["in_the_money"]]
        below = [float(row["strike"]) for row in puts if not row["in_the_money"]]
        if above and below:
            estimates.append((min(above) + max(below)) / 2)
    if estimates:
        return sum(estimates) / len(estimates)

    totals: dict[float, float] = {}
    for row in rows:
        oi = row.get("open_interest") or 0.0
        totals[float(row["strike"])] = totals.get(float(row["strike"]), 0.0) + oi
    return max(totals, key=totals.get) if totals else None


def _atm_rows(rows: list[Mapping[str, Any]], atm: float | None) -> list[Mapping[str, Any]]:
    if atm is None:
        return []
    by_type: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        option_type = str(row["option_type"])
        current = by_type.get(option_type)
        if current is None or abs(float(row["strike"]) - atm) < abs(float(current["strike"]) - atm):
            by_type[option_type] = row
    return list(by_type.values())


def _expiry_summary(
    expiry: str, rows: list[Mapping[str, Any]], price: float | None
) -> dict[str, Any]:
    calls = [row for row in rows if row["option_type"] == "call"]
    puts = [row for row in rows if row["option_type"] == "put"]
    call_oi = sum(row.get("open_interest") or 0.0 for row in calls)
    put_oi = sum(row.get("open_interest") or 0.0 for row in puts)
    call_volume = sum(row.get("volume") or 0.0 for row in calls)
    put_volume = sum(row.get("volume") or 0.0 for row in puts)
    atm = _atm_strike(rows, price)
    atms = _atm_rows(rows, atm)
    ivs = [row["implied_volatility"] for row in atms if row.get("implied_volatility") is not None]
    spreads = []
    for row in atms:
        bid, ask = row.get("bid"), row.get("ask")
        if bid is not None and ask is not None and ask >= bid:
            mid = (ask + bid) / 2
            if mid > 0:
                spreads.append((ask - bid) / mid)
    return {
        "expiry": expiry,
        "atm": atm,
        "atm_iv": sum(ivs) / len(ivs) if ivs else None,
        "atm_spread": sum(spreads) / len(spreads) if spreads else None,
        "call_oi": call_oi,
        "put_oi": put_oi,
        "call_volume": call_volume,
        "put_volume": put_volume,
        "pc_oi": _ratio(put_oi, call_oi),
        "pc_volume": _ratio(put_volume, call_volume),
    }


def _max_pain(rows: list[Mapping[str, Any]]) -> float | None:
    strikes = sorted({float(row["strike"]) for row in rows})
    if not strikes:
        return None
    calls = [(float(row["strike"]), row.get("open_interest") or 0.0)
             for row in rows if row["option_type"] == "call"]
    puts = [(float(row["strike"]), row.get("open_interest") or 0.0)
            for row in rows if row["option_type"] == "put"]
    pain: dict[float, float] = {}
    for settlement in strikes:
        pain[settlement] = (
            sum(max(0.0, settlement - strike) * oi for strike, oi in calls)
            + sum(max(0.0, strike - settlement) * oi for strike, oi in puts)
        )
    return min(pain, key=pain.get)


def _display_rows(rows: list[Mapping[str, Any]], summaries: list[dict[str, Any]]) -> list[Mapping[str, Any]]:
    selected: dict[tuple[str, float, str], Mapping[str, Any]] = {}
    by_expiry: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        by_expiry.setdefault(str(row["expiry"]), []).append(row)
    for summary in summaries:
        expiry = str(summary["expiry"])
        expiry_rows = by_expiry.get(expiry, [])
        for option_type in ("call", "put"):
            typed = [row for row in expiry_rows if row["option_type"] == option_type]
            atm = summary["atm"]
            if atm is None:
                continue
            ranked = sorted(typed, key=lambda row: abs(float(row["strike"]) - atm))
            for row in ranked[:8]:
                selected[(str(row["expiry"]), float(row["strike"]), str(row["option_type"]))] = row
    ranked_oi = sorted(
        rows,
        key=lambda row: (row.get("open_interest") or 0.0),
        reverse=True,
    )
    for row in ranked_oi[:8]:
        selected[(str(row["expiry"]), float(row["strike"]), str(row["option_type"]))] = row
    ordered = sorted(selected.values(), key=lambda row: (
        str(row["expiry"]), float(row["strike"]), str(row["option_type"])
    ))
    return ordered[:40]


def render_option_chain(evidence: OptionsEvidence) -> str:
    if not evidence.usable:
        return ""
    rows = list(evidence.observations)
    price = next((row.get("underlying_price") for row in rows
                  if row.get("underlying_price") is not None), None)
    expiries = sorted({str(row["expiry"]) for row in rows})
    summaries = [
        _expiry_summary(expiry, [row for row in rows if str(row["expiry"]) == expiry], price)
        for expiry in expiries
    ]

    total_call_oi = sum(item["call_oi"] for item in summaries)
    total_put_oi = sum(item["put_oi"] for item in summaries)
    total_call_volume = sum(item["call_volume"] for item in summaries)
    total_put_volume = sum(item["put_volume"] for item in summaries)
    top_oi: dict[float, float] = {}
    for row in rows:
        strike = float(row["strike"])
        top_oi[strike] = top_oi.get(strike, 0.0) + (row.get("open_interest") or 0.0)
    largest = sorted(top_oi.items(), key=lambda item: item[1], reverse=True)[:5]
    max_pain = _max_pain(rows)

    lines = [
        f"# Options chain evidence for {evidence.ticker} as of {evidence.trade_date}",
        "",
        f"Eligible observations: {len(rows)}; rejected before model input: {evidence.rejected}.",
        "",
        "## Deterministic summary",
        "",
        "| Expiry | ATM strike | ATM IV | ATM bid-ask spread | Call OI | Put OI | P/C OI | Call volume | Put volume | P/C volume |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in summaries:
        lines.append(
            f"| {item['expiry']} | {_fmt(item['atm'], 2)} | {_fmt(item['atm_iv'], 4)} | "
            f"{_fmt(item['atm_spread'], 4)} | {_fmt(item['call_oi'], 0)} | {_fmt(item['put_oi'], 0)} | "
            f"{_fmt(item['pc_oi'], 3)} | {_fmt(item['call_volume'], 0)} | "
            f"{_fmt(item['put_volume'], 0)} | {_fmt(item['pc_volume'], 3)} |"
        )
    lines.extend([
        "",
        f"- Total call open interest: {_fmt(total_call_oi, 0)}",
        f"- Total put open interest: {_fmt(total_put_oi, 0)}",
        f"- Put/call open-interest ratio: {_fmt(_ratio(total_put_oi, total_call_oi), 3)}",
        f"- Total call volume: {_fmt(total_call_volume, 0)}",
        f"- Total put volume: {_fmt(total_put_volume, 0)}",
        f"- Put/call volume ratio: {_fmt(_ratio(total_put_volume, total_call_volume), 3)}",
        f"- Largest open-interest strikes: {', '.join(f'{strike:g} ({oi:g})' for strike, oi in largest) or 'n/a'}",
        f"- Max-pain strike: {_fmt(max_pain, 2)}",
    ])
    if len(summaries) > 1:
        front, back = summaries[0]["atm_iv"], summaries[1]["atm_iv"]
        term = None if front is None or back is None else front - back
        lines.append(f"- ATM IV term structure (front minus next): {_fmt(term, 4)}")
    lines.extend([
        "",
        "## Observations used",
        "",
        "| Expiry | Type | Strike | Bid | Ask | Last | Volume | OI | IV | Snapshot |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ])
    for row in _display_rows(rows, summaries):
        lines.append(
            f"| {row['expiry']} | {row['option_type']} | {_fmt(row.get('strike'), 2)} | "
            f"{_fmt(row.get('bid'), 2)} | {_fmt(row.get('ask'), 2)} | {_fmt(row.get('last'), 2)} | "
            f"{_fmt(row.get('volume'), 0)} | {_fmt(row.get('open_interest'), 0)} | "
            f"{_fmt(row.get('implied_volatility'), 4)} | {row.get('snapshot_at')} |"
        )
    return "\n".join(lines)
