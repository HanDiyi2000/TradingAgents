"""Yahoo option-chain observations, stamped with the retrieval time."""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime
from typing import Any

import yfinance as yf

from tradingagents.dataflows.date_window import is_historical
from tradingagents.dataflows.errors import NoMarketDataError, VendorUnavailableError
from tradingagents.dataflows.symbols import normalize_symbol
from tradingagents.dataflows.vendors.yahoo.common import yf_retry

logger = logging.getLogger(__name__)

MAX_EXPIRIES = 2


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _flag(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return bool(value)


def _stamp(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)


def _underlying_price(ticker) -> float | None:
    try:
        return _number(ticker.fast_info["last_price"])
    except Exception:
        pass
    try:
        return _number(ticker.info.get("regularMarketPrice"))
    except Exception:
        return None


def _rows(frame, expiry: str, option_type: str, canonical: str,
          snapshot_at: str, retrieved_at: str, underlying_price: float | None) -> list[dict[str, Any]]:
    if frame is None or getattr(frame, "empty", True):
        return []
    rows = []
    for _, item in frame.iterrows():
        strike = _number(item.get("strike"))
        if strike is None:
            continue
        rows.append({
            "underlying": canonical,
            "underlying_price": underlying_price,
            "snapshot_at": snapshot_at,
            "retrieved_at": retrieved_at,
            "expiry": expiry,
            "strike": strike,
            "option_type": option_type,
            "contract_symbol": item.get("contractSymbol"),
            "bid": _number(item.get("bid")),
            "ask": _number(item.get("ask")),
            "last": _number(item.get("lastPrice")),
            "volume": _number(item.get("volume")),
            "open_interest": _number(item.get("openInterest")),
            "implied_volatility": _number(item.get("impliedVolatility")),
            "in_the_money": _flag(item.get("inTheMoney")),
            "last_trade_at": _stamp(item.get("lastTradeDate")),
            "source": "yfinance",
        })
    return rows


def get_option_chain(ticker: str, trade_date: str) -> list[dict[str, Any]]:
    canonical = normalize_symbol(ticker)
    if is_historical(trade_date):
        raise NoMarketDataError(
            ticker,
            canonical,
            "the yfinance option chain is a current snapshot with no historical availability",
        )

    source = yf.Ticker(canonical)
    expirations = yf_retry(lambda: source.options)
    if not expirations:
        raise NoMarketDataError(ticker, canonical, "no option expirations")

    selected = sorted(str(expiry) for expiry in expirations if str(expiry) >= trade_date)[:MAX_EXPIRIES]
    if not selected:
        raise NoMarketDataError(ticker, canonical, "no option expiration on or after the analysis date")

    retrieved_at = datetime.now(UTC).isoformat()
    snapshot_at = trade_date
    underlying_price = _underlying_price(source)
    observations: list[dict[str, Any]] = []
    for expiry in selected:
        try:
            chain = yf_retry(lambda expiry=expiry: source.option_chain(expiry))
        except VendorUnavailableError:
            if observations:
                logger.warning("Yahoo option chain failed for %s expiry %s after usable rows", canonical, expiry)
                break
            raise
        if chain is None:
            continue
        observations.extend(
            _rows(chain.calls, expiry, "call", canonical, snapshot_at, retrieved_at, underlying_price)
        )
        observations.extend(
            _rows(chain.puts, expiry, "put", canonical, snapshot_at, retrieved_at, underlying_price)
        )

    if not observations:
        raise NoMarketDataError(ticker, canonical, "no usable option contracts")
    return observations
