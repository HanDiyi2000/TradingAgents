"""Live yfinance option-chain smoke test for FEAT-01."""

import pytest

from tradingagents.dataflows.date_window import get_current_date
from tradingagents.dataflows.errors import NoMarketDataError
from tradingagents.dataflows.options import load_eligible_option_chain
from tradingagents.dataflows.vendors.yahoo.options import get_option_chain


@pytest.mark.integration
def test_current_option_chain_is_usable_through_the_adapter():
    trade_date = get_current_date()

    rows = get_option_chain("SPY", trade_date)
    evidence = load_eligible_option_chain("SPY", trade_date)

    assert rows
    assert all(row["underlying"] == "SPY" for row in rows)
    assert all(row["snapshot_at"] == trade_date for row in rows)
    assert any(row["open_interest"] is not None for row in rows)
    assert evidence.usable
    assert evidence.rejected == 0


@pytest.mark.integration
def test_historical_live_request_is_refused_before_any_fetch():
    with pytest.raises(NoMarketDataError, match="no historical availability"):
        get_option_chain("SPY", "2020-01-02")
