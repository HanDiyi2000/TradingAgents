"""Eligible option evidence is filtered before any model sees it."""

from __future__ import annotations

import pandas as pd
import pytest

from tradingagents.dataflows import options, router
from tradingagents.dataflows.config import set_config
from tradingagents.dataflows.errors import NoMarketDataError
from tradingagents.dataflows.vendors.yahoo import options as yahoo_options
from tradingagents.default_config import DEFAULT_CONFIG

CUTOFF = "2026-01-09"
NOTICE = (
    f"Options data unavailable for NVDA as of {CUTOFF}. No eligible option-chain "
    "observations were available for this instrument on that date. This report "
    "contains no options evidence and no inferred options signal."
)


def _record(**overrides):
    base = {
        "underlying": "NVDA",
        "snapshot_at": f"{CUTOFF}T12:00:00+00:00",
        "expiry": "2026-02-20",
        "strike": 100.0,
        "option_type": "call",
        "bid": 1.00,
        "ask": 1.20,
        "last": 1.10,
        "volume": 10.0,
        "open_interest": 100.0,
        "implied_volatility": 0.25,
        "underlying_price": 101.0,
        "in_the_money": True,
        "source": "fixture",
    }
    base.update(overrides)
    return base


def _evidence(records):
    rows, rejected, reasons = options.eligible_observations("NVDA", CUTOFF, records)
    return options.OptionsEvidence("NVDA", CUTOFF, rows, rejected, reasons)


def test_adapter_keeps_only_matching_and_cutoff_eligible_records():
    records = [
        _record(strike=100.0),
        _record(strike=999.0, snapshot_at="2026-01-10T00:00:00+00:00"),
        _record(strike=101.0, underlying="MSFT"),
        _record(strike=102.0, snapshot_at=None),
        _record(strike=103.0, snapshot_at="2026-01-09T12:00:00"),
    ]

    evidence = _evidence(records)

    assert [row["strike"] for row in evidence.observations] == [100.0]
    assert evidence.rejected == 4
    rendered = options.render_option_chain(evidence)
    assert "999.00" not in rendered
    assert "100.00" in rendered


def test_record_at_cutoff_is_eligible():
    records = [
        _record(strike=100.0, snapshot_at=f"{CUTOFF}T23:59:59+00:00"),
        _record(strike=105.0, snapshot_at="2026-01-10T00:00:00+00:00"),
    ]

    evidence = _evidence(records)

    assert [row["strike"] for row in evidence.observations] == [100.0]
    assert evidence.rejected == 1


def test_date_only_snapshot_is_eligible():
    evidence = _evidence([_record(snapshot_at=CUTOFF)])

    assert evidence.usable
    assert evidence.observations[0]["strike"] == 100.0


def test_duplicate_contract_keeps_latest_eligible_observation():
    records = [
        _record(strike=100.0, snapshot_at="2026-01-08T12:00:00+00:00", bid=1.0),
        _record(strike=100.0, snapshot_at=f"{CUTOFF}T12:00:00+00:00", bid=2.0),
    ]

    evidence = _evidence(records)

    assert len(evidence.observations) == 1
    assert evidence.observations[0]["bid"] == 2.0
    assert evidence.rejected == 1


def test_naive_timestamp_is_unverifiable():
    evidence = _evidence([_record(snapshot_at="2026-01-09T12:00:00")])

    assert not evidence.usable
    assert evidence.rejected == 1


def test_only_rejected_records_trigger_unavailable(monkeypatch):
    monkeypatch.setattr(
        options,
        "route_to_vendor",
        lambda *a, **k: [_record(underlying="MSFT"), _record(snapshot_at="2026-01-10")],
    )

    evidence = options.load_eligible_option_chain("NVDA", CUTOFF)

    assert not evidence.usable
    assert options.unavailable_options_notice("NVDA", CUTOFF) == NOTICE


def test_provider_failure_is_unavailable(monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr(options, "route_to_vendor", explode)

    evidence = options.load_eligible_option_chain("NVDA", CUTOFF)

    assert not evidence.usable
    assert evidence.provider_note == "RuntimeError"


def test_provider_sentinel_is_unavailable(monkeypatch):
    monkeypatch.setattr(options, "route_to_vendor", lambda *a, **k: "DATA_UNAVAILABLE: no vendor")

    evidence = options.load_eligible_option_chain("NVDA", CUTOFF)

    assert not evidence.usable


def test_rendered_evidence_contains_the_approved_indicator_set():
    records = [
        _record(strike=100.0, in_the_money=True, implied_volatility=0.30, bid=2.0, ask=2.2),
        _record(strike=105.0, in_the_money=False, implied_volatility=0.28, bid=0.8, ask=0.9,
                option_type="put", open_interest=80.0, volume=8.0),
        _record(strike=100.0, in_the_money=True, implied_volatility=0.32, bid=2.1, ask=2.3,
                option_type="put", open_interest=120.0, volume=12.0),
        _record(strike=105.0, in_the_money=False, implied_volatility=0.26, bid=0.7, ask=0.8,
                expiry="2026-03-20", open_interest=60.0, volume=6.0),
        _record(strike=100.0, in_the_money=True, implied_volatility=0.34, bid=2.4, ask=2.6,
                expiry="2026-03-20", option_type="put", open_interest=90.0, volume=9.0),
    ]

    rendered = options.render_option_chain(_evidence(records))

    assert "ATM IV" in rendered
    assert "Put/call open-interest ratio" in rendered
    assert "Put/call volume ratio" in rendered
    assert "Max-pain strike" in rendered
    assert "ATM IV term structure" in rendered
    assert "2026-02-20" in rendered and "2026-03-20" in rendered


def test_yfinance_historical_chain_is_refused(monkeypatch):
    monkeypatch.setattr(yahoo_options, "is_historical", lambda trade_date: True)

    with pytest.raises(NoMarketDataError, match="no historical availability"):
        yahoo_options.get_option_chain("NVDA", CUTOFF)


def test_historical_run_falls_back_to_unavailable_through_the_router(monkeypatch):
    set_config({"data_vendors": {"options_data": "yfinance"}})
    monkeypatch.setattr(yahoo_options, "is_historical", lambda trade_date: True)

    evidence = options.load_eligible_option_chain("NVDA", CUTOFF)

    assert not evidence.usable
    assert options.unavailable_options_notice("NVDA", CUTOFF) == NOTICE


def test_yfinance_current_chain_is_stamped(monkeypatch):
    calls = pd.DataFrame([{
        "contractSymbol": "NVDA260116C00100000",
        "strike": 100.0,
        "bid": 1.0,
        "ask": 1.2,
        "lastPrice": 1.1,
        "volume": 10,
        "openInterest": 100,
        "impliedVolatility": 0.25,
        "inTheMoney": True,
        "lastTradeDate": pd.Timestamp("2026-11-21T15:59:00-05:00"),
    }])
    puts = pd.DataFrame([{
        "contractSymbol": "NVDA260116P00100000",
        "strike": 100.0,
        "bid": 2.0,
        "ask": 2.2,
        "lastPrice": 2.1,
        "volume": 5,
        "openInterest": 80,
        "impliedVolatility": 0.27,
        "inTheMoney": False,
        "lastTradeDate": pd.Timestamp("2026-11-21T15:59:00-05:00"),
    }])

    class Chain:
        pass

    class FakeTicker:
        options = ["2026-12-18"]
        fast_info = {"last_price": 101.0}

        def option_chain(self, expiry):
            chain = Chain()
            chain.calls = calls
            chain.puts = puts
            return chain

    monkeypatch.setattr(yahoo_options, "is_historical", lambda trade_date: False)
    monkeypatch.setattr(yahoo_options.yf, "Ticker", lambda symbol: FakeTicker())
    monkeypatch.setattr(yahoo_options, "yf_retry", lambda func: func())

    rows = yahoo_options.get_option_chain("NVDA", "2026-11-22")

    assert len(rows) == 2
    assert {row["option_type"] for row in rows} == {"call", "put"}
    assert rows[0]["underlying"] == "NVDA"
    assert rows[0]["snapshot_at"] == "2026-11-22"
    assert rows[0]["retrieved_at"].endswith("+00:00")


def test_default_options_category_uses_yfinance():
    assert DEFAULT_CONFIG["data_vendors"]["options_data"] == "yfinance"
    assert "yfinance" in router.VENDOR_METHODS["get_option_chain"]
