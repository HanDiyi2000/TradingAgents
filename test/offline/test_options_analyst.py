"""The Options Analyst, its defaults, delivery, presentation and unavailable path."""

from __future__ import annotations

import copy
import inspect
import json

import pandas as pd
import pytest
from langchain_core.messages import AIMessage

from cli import prompts
from cli.display import MessageBuffer, display_complete_report, update_analyst_statuses
from cli.models import AnalystType, AssetType
from cli.prefs import sanitize
from offline.test_graph_end_to_end import ScriptedModel
from tradingagents.agents import context
from tradingagents.agents.analysts import sentiment_analyst
from tradingagents.agents.analysts.options_analyst import create_options_analyst
from tradingagents.agents.researchers.bear_researcher import create_bear_researcher
from tradingagents.agents.researchers.bull_researcher import create_bull_researcher
from tradingagents.agents.risk_mgmt.aggressive_debator import create_aggressive_debator
from tradingagents.agents.risk_mgmt.conservative_debator import create_conservative_debator
from tradingagents.agents.risk_mgmt.neutral_debator import create_neutral_debator
from tradingagents.backtest import run_backtest
from tradingagents.dataflows import options, router
from tradingagents.dataflows.vendors.yahoo import market as yahoo_market, snapshot
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph import trading_graph
from tradingagents.graph.analyst_execution import build_analyst_execution_plan
from tradingagents.graph.setup import GraphSetup
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.reporting import write_report_tree

CUTOFF = "2026-01-09"
OPTIONS_TAG = "OPTIONS_EVIDENCE_TAG_7f31"
REPORT = "Options report grounded in the supplied chain."
NOTICE = (
    f"Options data unavailable for NVDA as of {CUTOFF}. No eligible option-chain "
    "observations were available for this instrument on that date. This report "
    "contains no options evidence and no inferred options signal."
)


@pytest.fixture
def offline(monkeypatch):
    called = set()
    for method, vendors in router.VENDOR_METHODS.items():
        for vendor in vendors:
            monkeypatch.setitem(
                vendors, vendor,
                lambda *a, _method=method, **k: called.add(_method) or f"{_method} data",
            )
    prices = pd.DataFrame({
        "Date": pd.bdate_range(end=CUTOFF, periods=60),
        "Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.5, "Volume": 1_000_000,
    })
    monkeypatch.setattr(snapshot, "load_ohlcv", lambda *a, **k: called.add("ohlcv") or prices.copy())
    monkeypatch.setattr(sentiment_analyst, "fetch_stocktwits_messages", lambda *a, **k: "no posts")
    monkeypatch.setattr(sentiment_analyst, "fetch_reddit_posts", lambda *a, **k: "no posts")
    monkeypatch.setattr(
        yahoo_market.yf, "Ticker",
        lambda symbol: type("T", (), {"info": {"longName": "NVIDIA"}})(),
    )
    context._identity.cache_clear()
    return called


def _record(**overrides):
    base = {
        "underlying": "NVDA",
        "snapshot_at": f"{CUTOFF}T12:00:00+00:00",
        "expiry": "2026-02-20",
        "strike": 100.0,
        "option_type": "call",
        "bid": 1.0,
        "ask": 1.2,
        "last": 1.1,
        "volume": 10.0,
        "open_interest": 100.0,
        "implied_volatility": 0.25,
        "underlying_price": 101.0,
        "in_the_money": True,
        "source": "fixture",
    }
    base.update(overrides)
    return base


def _prompt_text(prompt) -> str:
    if isinstance(prompt, str):
        return prompt
    parts = []
    for message in prompt:
        content = message.content if hasattr(message, "content") else str(message)
        parts.append(str(content))
    return "\n".join(parts)


class CapturingLLM:
    def __init__(self, response=REPORT):
        self.response = response
        self.prompts: list[str] = []

    def invoke(self, prompt, *args, **kwargs):
        self.prompts.append(_prompt_text(prompt))
        return AIMessage(content=self.response)

    def with_structured_output(self, *args, **kwargs):
        raise NotImplementedError


class FailingLLM:
    def invoke(self, *args, **kwargs):
        raise AssertionError("the unavailable path must not call the model")


def _base_state():
    return {
        "company_of_interest": "NVDA",
        "trade_date": CUTOFF,
        "asset_type": "stock",
        "instrument_context": "The instrument to analyze is `NVDA`.",
        "messages": [],
        "market_report": "Market report.",
        "sentiment_report": "Sentiment report.",
        "news_report": "News report.",
        "fundamentals_report": "Fundamentals report.",
        "options_report": OPTIONS_TAG,
        "investment_plan": "Investment plan.",
        "trader_investment_plan": "Trader plan.",
        "investment_debate_state": {
            "bull_history": "", "bear_history": "", "history": "",
            "current_response": "", "count": 0,
        },
        "risk_debate_state": {
            "aggressive_history": "", "conservative_history": "",
            "neutral_history": "", "history": "", "latest_speaker": "",
            "current_aggressive_response": "", "current_conservative_response": "",
            "current_neutral_response": "", "count": 0,
        },
    }


def _plan_keys(keys):
    return [spec.key for spec in build_analyst_execution_plan(keys).specs]


def test_stock_defaults_include_the_original_four_plus_options():
    expected = ("market", "social", "news", "fundamentals", "options")
    assert inspect.signature(TradingAgentsGraph.__init__).parameters[
        "selected_analysts"
    ].default == expected
    assert inspect.signature(GraphSetup.setup_graph).parameters[
        "selected_analysts"
    ].default == expected
    assert inspect.signature(run_backtest).parameters["selected_analysts"].default == expected


def _capture_analyst_choices(monkeypatch):
    captured = {}

    class FakeQuestion:
        def __init__(self, choices):
            self.choices = choices

        def ask(self):
            return [choice.value for choice in self.choices if choice.checked]

    def fake_checkbox(message, choices, **kwargs):
        captured["choices"] = choices
        return FakeQuestion(choices)

    monkeypatch.setattr(prompts.questionary, "checkbox", fake_checkbox)
    return captured


def test_fresh_stock_cli_preselects_five_and_saved_four_stays_four(monkeypatch):
    captured = _capture_analyst_choices(monkeypatch)

    fresh = prompts.select_analysts(AssetType.STOCK)
    assert [analyst.value for analyst in fresh] == [
        "market", "social", "news", "fundamentals", "options",
    ]
    assert [choice.value.value for choice in captured["choices"] if choice.checked] == [
        "market", "social", "news", "fundamentals", "options",
    ]

    saved = prompts.select_analysts(
        AssetType.STOCK,
        default=["market", "social", "news", "fundamentals"],
    )
    assert [analyst.value for analyst in saved] == [
        "market", "social", "news", "fundamentals",
    ]


def test_crypto_defaults_exclude_options(monkeypatch):
    captured = _capture_analyst_choices(monkeypatch)

    selected = prompts.select_analysts(AssetType.CRYPTO)

    assert [analyst.value for analyst in selected] == ["market", "social", "news"]
    assert all(choice.value is not AnalystType.OPTIONS for choice in captured["choices"])


def test_saved_preferences_keep_the_original_four_and_drop_options_for_crypto():
    kept = sanitize(
        {"analysts": ["market", "social", "news", "fundamentals"]}, "stock"
    )
    assert kept["analysts"] == ["market", "social", "news", "fundamentals"]

    kept = sanitize(
        {"analysts": ["market", "social", "news", "fundamentals", "options"]}, "stock"
    )
    assert kept["analysts"] == ["market", "social", "news", "fundamentals", "options"]

    kept = sanitize(
        {"analysts": ["market", "social", "news", "fundamentals", "options"]}, "crypto"
    )
    assert kept["analysts"] == ["market", "social", "news"]


def test_explicit_options_only_and_original_four_selections():
    assert prompts.parse_analysts("options", AssetType.STOCK) == [AnalystType.OPTIONS]
    assert _plan_keys(["options"]) == ["options"]
    assert _plan_keys(["market", "social", "news", "fundamentals"]) == [
        "market", "social", "news", "fundamentals",
    ]
    with pytest.raises(ValueError, match="not available for crypto"):
        prompts.parse_analysts("options", AssetType.CRYPTO)


def test_options_spec_names_the_public_contract():
    spec = build_analyst_execution_plan(["options"]).specs[0]

    assert spec.key == "options"
    assert spec.agent_node == "Options Analyst"
    assert spec.report_key == "options_report"


def _selected_graph(tmp_path, monkeypatch, model, selected=("options",), **config):
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg.update(
        results_dir=str(tmp_path / "results"),
        data_cache_dir=str(tmp_path / "cache"),
        memory_log_path=str(tmp_path / "log.md"),
        **config,
    )
    monkeypatch.setattr(
        trading_graph, "create_tier_client", lambda config, tier, **kw: _Client(model)
    )
    return trading_graph.TradingAgentsGraph(selected, config=cfg)


class _Client:
    def __init__(self, model):
        self.model = model

    def get_llm(self):
        return self.model


@pytest.mark.unit
def test_options_only_run_still_reaches_a_decision(tmp_path, monkeypatch, offline):
    monkeypatch.setitem(
        router.VENDOR_METHODS["get_option_chain"], "yfinance", lambda *a, **k: [_record()]
    )
    model = ScriptedModel(structured=True)
    graph = _selected_graph(tmp_path, monkeypatch, model)

    state, signal = graph.propagate("NVDA", CUTOFF)

    assert signal == state["final_rating"] == "Overweight"
    assert state["options_report"].strip()
    assert state["options_report"] != NOTICE
    assert "Options Analyst" in graph.graph.get_graph().nodes
    assert "Market Analyst" not in graph.graph.get_graph().nodes


@pytest.mark.unit
def test_options_report_reaches_bull_bear_and_three_risk_debaters():
    state = _base_state()
    factories = [
        create_bull_researcher,
        create_bear_researcher,
        create_aggressive_debator,
        create_conservative_debator,
        create_neutral_debator,
    ]

    for factory in factories:
        llm = CapturingLLM()
        factory(llm)(state)
        assert OPTIONS_TAG in llm.prompts[-1]


def test_deselected_options_report_is_absent_not_invented():
    state = _base_state()
    state["options_report"] = ""
    llm = CapturingLLM()

    create_bull_researcher(llm)(state)

    assert "No options report in this run" in llm.prompts[-1]
    assert OPTIONS_TAG not in llm.prompts[-1]


def test_deselected_options_makes_no_lookup_or_report(tmp_path, monkeypatch, offline):
    calls = []
    monkeypatch.setattr(
        options, "load_eligible_option_chain",
        lambda *a, **k: calls.append(a) or options.OptionsEvidence("NVDA", CUTOFF, ()),
    )
    graph = _selected_graph(
        tmp_path, monkeypatch, ScriptedModel(structured=True),
        selected=("market", "social", "news", "fundamentals"),
    )

    state, signal = graph.propagate("NVDA", CUTOFF)

    assert signal == state["final_rating"] == "Overweight"
    assert calls == []
    assert state["options_report"] == ""
    write_report_tree(state, "NVDA", tmp_path / "report", settings={}, html=True)
    assert not (tmp_path / "report" / "1_analysts" / "options.md").exists()


def test_rendered_chain_reaches_the_options_model_input(monkeypatch):
    monkeypatch.setattr(options, "route_to_vendor", lambda *a, **k: [_record(strike=123.45)])
    llm = CapturingLLM()

    result = create_options_analyst(llm)(
        {
            "company_of_interest": "NVDA",
            "trade_date": CUTOFF,
            "instrument_context": "The instrument to analyze is `NVDA`.",
            "messages": [],
        }
    )

    assert result["options_report"] == REPORT
    assert "123.45" in llm.prompts[-1]
    assert "You are the Options Analyst" in llm.prompts[-1]


def test_future_snapshot_never_reaches_the_options_model(monkeypatch):
    monkeypatch.setattr(
        options,
        "route_to_vendor",
        lambda *a, **k: [
            _record(strike=100.0),
            _record(strike=999.0, snapshot_at="2026-01-10T00:00:00+00:00"),
        ],
    )
    llm = CapturingLLM()

    create_options_analyst(llm)(
        {
            "company_of_interest": "NVDA",
            "trade_date": CUTOFF,
            "instrument_context": "The instrument to analyze is `NVDA`.",
            "messages": [],
        }
    )

    assert "999.00" not in llm.prompts[-1]
    assert "100.00" in llm.prompts[-1]


@pytest.mark.parametrize("mode", ["empty", "failure", "historical"])
def test_unavailable_notice_reaches_outputs_without_a_model_call(monkeypatch, tmp_path, mode):
    def provider(*args, **kwargs):
        if mode == "failure":
            raise RuntimeError("provider down")
        return []

    monkeypatch.setattr(options, "route_to_vendor", provider)
    result = create_options_analyst(FailingLLM())(
        {
            "company_of_interest": "NVDA",
            "trade_date": CUTOFF,
            "instrument_context": "The instrument to analyze is `NVDA`.",
            "messages": [],
        }
    )

    assert result["options_report"] == NOTICE

    state = _base_state()
    state["options_report"] = NOTICE
    for factory in (
        create_bull_researcher, create_bear_researcher, create_aggressive_debator,
        create_conservative_debator, create_neutral_debator,
    ):
        llm = CapturingLLM()
        factory(llm)(state)
        assert NOTICE in llm.prompts[-1]

    write_report_tree(state, "NVDA", tmp_path / "report", settings={}, html=True)
    saved = (tmp_path / "report" / "1_analysts" / "options.md").read_text(encoding="utf-8")
    assert saved == NOTICE


def test_unavailable_notice_carries_no_inferred_signal():
    for token in ("IV", "strike", "put/call", "Buy", "Sell", "%"):
        assert token not in NOTICE


def test_options_report_reaches_cli_state_log_and_report_tree(tmp_path, monkeypatch):
    state = _base_state()
    state["final_trade_decision"] = "**Rating**: Buy"

    report_dir = tmp_path / "report"
    write_report_tree(state, "NVDA", report_dir, settings={}, html=True)
    assert (report_dir / "1_analysts" / "options.md").read_text(encoding="utf-8") == OPTIONS_TAG
    assert OPTIONS_TAG in (report_dir / "complete_report.md").read_text(encoding="utf-8")
    assert OPTIONS_TAG in (report_dir / "complete_report.html").read_text(encoding="utf-8")

    buffer = MessageBuffer()
    buffer.init_for_analysis(["options"])
    update_analyst_statuses(buffer, {"options_report": OPTIONS_TAG})
    assert buffer.agent_status["Options Analyst"] == "completed"
    assert buffer.report_sections["options_report"] == OPTIONS_TAG

    graph = object.__new__(TradingAgentsGraph)
    graph.config = {"results_dir": str(tmp_path / "logs")}
    graph.selected_analysts = ("options",)
    graph._log_state(CUTOFF, state)
    log = json.loads(next((tmp_path / "logs").rglob("full_states_log*.json")).read_text())
    assert log["options_report"] == OPTIONS_TAG

    api_dir = tmp_path / "api"
    TradingAgentsGraph.save_reports(graph, state, "NVDA", save_path=api_dir, html=True)
    assert (api_dir / "1_analysts" / "options.md").exists()
    assert (api_dir / "complete_report.html").exists()


def test_baseline_state_without_options_field_still_exports(tmp_path):
    state = _base_state()
    state.pop("options_report")

    write_report_tree(state, "NVDA", tmp_path, settings={}, html=True)

    assert not (tmp_path / "1_analysts" / "options.md").exists()
    assert (tmp_path / "complete_report.md").exists()


def test_blank_options_report_writes_no_section(tmp_path):
    state = _base_state()
    state["options_report"] = ""

    write_report_tree(state, "NVDA", tmp_path, settings={}, html=True)

    assert not (tmp_path / "1_analysts" / "options.md").exists()
    assert "Options Analyst" not in (tmp_path / "complete_report.md").read_text(encoding="utf-8")


def test_cli_complete_report_shows_options(capsys):
    state = _base_state()

    display_complete_report(state)

    output = capsys.readouterr().out
    assert "Options Analyst" in output
    assert OPTIONS_TAG in output
