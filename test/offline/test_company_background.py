"""FEAT-03 / FR-RPT-01: a Company Background section in the consolidated report.

The report must carry one factual introduction drawn from the run's retained
company profile, between the header and the numbered analyst sections, offered
in both Markdown and the requested HTML. It is found without the Fundamentals
Analyst and with no extra agent or model call. A run's profile is captured once
at initialization (the single existing identity lookup) and kept on the run
state as ``company_identity``; the exporter reads only stored run data, never
the network or the identity cache.

Coverage here is behaviour-based:
- initialization retains the cleaned profile from the one lookup, reusing the
  cache when the context was already resolved, and does not bypass
  ``resolve_instrument_context``;
- the retained profile survives the graph-state flow into final-state export;
- the profile is persisted in the run log;
- both export entry points (``TradingAgentsGraph.save_reports`` and the CLI
  ``run._offer_reports`` with non-interactive flags) write files whose contents
  carry the background in both formats;
- the section is exactly one, placed after the header and before the numbered
  analyst sections;
- historical runs label the current name and omit undated details in both
  formats; a historical run without a name shows the notice and leaks nothing;
- missing profiles show an unavailable notice and still export;
- the exporter performs no lookup, cache access or model call.

Vendors are stubbed for graph-running tests so nothing reaches the network.
The clock is frozen so historical/current semantics are deterministic, and the
identity cache is cleared before and after the affected tests.

No implementation of this feature exists yet, so most cases are expected to
fail until FEAT-03 lands.
"""

from __future__ import annotations

import copy
import json
import re

import pandas as pd
import pytest
from markdown_it import MarkdownIt

from cli import run as cli_run
from offline.test_graph_end_to_end import ScriptedModel
from tradingagents.agents import context
from tradingagents.agents.analysts import sentiment_analyst
from tradingagents.dataflows import router
from tradingagents.dataflows.date_window import get_current_date
from tradingagents.dataflows.vendors.yahoo import market as yahoo_market
from tradingagents.dataflows.vendors.yahoo import snapshot
from tradingagents.graph import trading_graph
from tradingagents.dataflows.config import set_config
from tradingagents.default_config import DEFAULT_CONFIG

# A fixed clock. All date-sensitive code reads ``get_current_date`` (via
# ``date_window.is_historical`` and ``trading_graph._validate_trade_date``), so
# patching it once makes current/historical deterministic.
TODAY = "2026-06-15"
PAST = "2024-05-10"
TRADE_DATE = TODAY

PROFILE_FIELDS = {"company_name", "industry", "business_description"}

FULL_INFO = {
    "longName": "NVIDIA Corporation",
    "industry": "Semiconductors",
    "longBusinessSummary": (
        "NVIDIA Corporation provides graphics and compute solutions worldwide. "
        "The company also sells networking equipment and software."
    ),
}
DESCRIPTION_TWO = FULL_INFO["longBusinessSummary"]


# --------------------------------------------------------------------------- #
# Fixtures and helpers
# --------------------------------------------------------------------------- #

@pytest.fixture(autouse=True)
def _fixed_clock(monkeypatch):
    """Freeze today's date at the point every date-sensitive path reads it."""
    from tradingagents.dataflows import date_window

    monkeypatch.setattr(date_window, "get_current_date", lambda: TODAY)
    monkeypatch.setattr(trading_graph, "get_current_date", lambda: TODAY)


@pytest.fixture(autouse=True)
def _clean_identity_cache():
    """A stub profile must not leak into other tests (and vice versa)."""
    context._identity.cache_clear()
    yield
    context._identity.cache_clear()


@pytest.fixture
def offline(monkeypatch):
    """Every router vendor answers offline; analysts need no network."""
    called: set[str] = set()
    for method, vendors in router.VENDOR_METHODS.items():
        for vendor in vendors:
            monkeypatch.setitem(
                vendors, vendor,
                lambda *a, _m=method, **k: called.add(_m) or f"{_m} data",
            )
    prices = pd.DataFrame({
        "Date": pd.bdate_range(end=TRADE_DATE, periods=60),
        "Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.5, "Volume": 1_000_000,
    })
    monkeypatch.setattr(snapshot, "load_ohlcv", lambda *a, **k: called.add("ohlcv") or prices.copy())
    monkeypatch.setattr(sentiment_analyst, "fetch_stocktwits_messages", lambda *a, **k: "no posts")
    monkeypatch.setattr(sentiment_analyst, "fetch_reddit_posts", lambda *a, **k: "no posts")
    monkeypatch.setattr(
        yahoo_market.yf, "Ticker",
        lambda symbol: type("T", (), {"info": {"longName": "NVIDIA Corporation"}})(),
    )
    return called


class _ProfileSpy:
    """Stands in for the single identity lookup and counts its invocations."""

    def __init__(self, info):
        self.info = info
        self.calls = 0

    def __call__(self, ticker):
        self.calls += 1
        return dict(self.info)


def _spy(monkeypatch, info):
    """Replace the run's single profile lookup; clear the cache for isolation."""
    spy = _ProfileSpy(info)
    monkeypatch.setattr(context, "get_company_profile", spy)
    context._identity.cache_clear()
    return spy


def _forbid_lookups(monkeypatch):
    """Make any identity lookup or cache access during export fail loudly.

    The replacement exposes ``cache_clear`` so the cache-hygiene fixture can clear
    it on teardown.
    """
    def _forbidden(*a, **k):
        raise AssertionError("the export path must not look up or cache identity")

    _forbidden.cache_clear = lambda: None
    monkeypatch.setattr(context, "get_company_profile", _forbidden)
    monkeypatch.setattr(context, "_identity", _forbidden)


class _LocalClient:
    def __init__(self, model):
        self.model = model

    def get_llm(self):
        return self.model


def _graph(tmp_path, monkeypatch, model, selected=("market", "news")):
    """A graph with an explicit analyst selection; LLM clients are patched.

    Vendors are stubbed by the ``offline`` fixture, which graph tests request.
    """
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg.update(
        results_dir=str(tmp_path / "results"),
        data_cache_dir=str(tmp_path / "cache"),
        memory_log_path=str(tmp_path / "log.md"),
    )
    monkeypatch.setattr(
        trading_graph, "create_tier_client",
        lambda config, tier, **k: _LocalClient(model),
    )
    return trading_graph.TradingAgentsGraph(selected, config=cfg)


def _export_state(**overrides):
    """A completed run's final state for export-only cases."""
    state = {
        "company_of_interest": "NVDA",
        "trade_date": TODAY,
        "asset_type": "stock",
        "market_report": "MARKET REPORT BODY",
        "news_report": "NEWS REPORT BODY",
        "investment_debate_state": {
            "bull_history": "", "bear_history": "", "history": "",
            "current_response": "", "count": 0,
        },
        "investment_plan": "PLAN",
        "trader_investment_plan": "TRADE",
        "risk_debate_state": {
            "aggressive_history": "", "conservative_history": "", "neutral_history": "",
            "history": "", "latest_speaker": "", "current_aggressive_response": "",
            "current_conservative_response": "", "current_neutral_response": "", "count": 0,
        },
        "final_trade_decision": "**Rating**: Overweight\n\nThe final decision stands.",
    }
    state.update(overrides)
    return state


def _markdown_sections(markdown: str):
    """Return {level-2 heading text: body} for the report's ``## `` sections."""
    parts = re.split(r"^## (.+)$", markdown, flags=re.MULTILINE)
    # parts = [preamble, heading1, body1, heading2, body2, ...]
    sections = {}
    for i in range(1, len(parts), 2):
        sections[parts[i].strip()] = parts[i + 1]
    return sections


def _background_markdown(markdown: str) -> str:
    """The one Company Background section body, asserting exactly one exists."""
    matches = re.findall(
        r"^##\s+Company Background\s*$(.*?)(?=^##\s|\Z)",
        markdown, flags=re.MULTILINE | re.DOTALL,
    )
    assert len(matches) == 1, f"expected exactly one Company Background section, got {len(matches)}"
    return matches[0]


def _background_html(page: str) -> str:
    """The HTML Company Background block, asserting exactly one exists.

    The exporter is free to place the block in its own ``<section>``; we accept a
    section or heading anchor and bound the fragment to the next section/heading.
    """
    blocks = re.findall(
        r"(<section[^>]*>\s*<h2[^>]*>\s*Company Background\s*</h2>.*?</section>)",
        page, flags=re.IGNORECASE | re.DOTALL,
    )
    if not blocks:
        # Fallback: a heading followed by content up to the next <section>/<h2>.
        blocks = re.findall(
            r"(<h2[^>]*>\s*Company Background\s*</h2>.*?)(?=<section|<h2|</main>)",
            page, flags=re.IGNORECASE | re.DOTALL,
        )
    assert len(blocks) == 1, f"expected exactly one HTML Company Background block, got {len(blocks)}"
    return blocks[0]


def _html_text(fragment: str) -> str:
    """Visible text of an HTML fragment (tags stripped, entities lightly unwrapped)."""
    text = re.sub(r"<[^>]+>", " ", fragment)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return re.sub(r"\s+", " ", text).strip()


def _write_via_save_reports(graph, state, ticker="NVDA"):
    """Export through the Python entry point; return the Markdown and HTML text."""
    path = graph.save_reports(state, ticker, html=True)
    markdown = path.read_text(encoding="utf-8")
    page = path.with_name("complete_report.html").read_text(encoding="utf-8")
    return markdown, page


def _md_visible_text(markdown_fragment: str) -> str:
    """What a reader sees of a Markdown fragment, rendered as the page does.

    Uses the same CommonMark renderer the HTML exporter uses (raw HTML off), so
    formatting characters a reader would not see as themselves (``*`` for
    emphasis, ``<...>``, ``[x](y)`` links) are interpreted the way a reader would
    see them; the result is tag-stripped visible text.
    """
    md = MarkdownIt("commonmark", {"html": False}).disable("image")
    return _html_text(md.render(markdown_fragment))



def _write_via_cli(tmp_path, state, graph, monkeypatch):
    """Export through the CLI ``_offer_reports`` entry with non-interactive flags."""
    # No prompt may run: save/html/show are given explicitly.
    def _no_prompt(*a, **k):
        raise AssertionError("_offer_reports must not prompt when save/html/show are given")

    monkeypatch.setattr(cli_run.typer, "prompt", _no_prompt)
    monkeypatch.setattr(cli_run, "display_complete_report", lambda *a, **k: None)
    # Pin the report directory so we read exactly this run's files.
    out_dir = tmp_path / "cli_reports"
    monkeypatch.setattr(graph, "default_report_path", lambda ticker: out_dir)

    cli_run._offer_reports(state, graph, state["company_of_interest"],
                           save=True, show=False, html=True)

    markdown = (out_dir / "complete_report.md").read_text(encoding="utf-8")
    page = (out_dir / "complete_report.html").read_text(encoding="utf-8")
    return markdown, page


# --------------------------------------------------------------------------- #
# Initialization: the one lookup is retained; cache is reused, not re-fetched
# --------------------------------------------------------------------------- #

@pytest.mark.unit
def test_initialization_retains_the_cleaned_profile_from_one_lookup(tmp_path, monkeypatch):
    """create_run_state keeps name, industry and description from a single lookup."""
    spy = _spy(monkeypatch, FULL_INFO)
    graph = _graph(tmp_path, monkeypatch, ScriptedModel(structured=True))

    state = graph.create_run_state("NVDA", TODAY)

    assert spy.calls == 1
    identity = state.get("company_identity")
    assert isinstance(identity, dict)
    assert identity["company_name"] == "NVIDIA Corporation"
    assert identity["industry"] == "Semiconductors"
    assert identity["business_description"] == DESCRIPTION_TWO


@pytest.mark.unit
def test_initialization_retains_only_the_cleaned_profile_fields(tmp_path, monkeypatch):
    """company_identity holds only name, industry and description."""
    _spy(monkeypatch, {**FULL_INFO, "sector": "Technology", "exchange": "NMS"})
    graph = _graph(tmp_path, monkeypatch, ScriptedModel(structured=True))

    identity = graph.create_run_state("NVDA", TODAY)["company_identity"]

    assert set(identity) == PROFILE_FIELDS
    assert "Technology" not in identity.values() and "NMS" not in identity.values()


@pytest.mark.unit
@pytest.mark.parametrize("placeholder", ["", "  ", "None", "n/a", "NAN", "null"])
def test_initialization_omits_placeholder_profile_values(tmp_path, monkeypatch, placeholder):
    """Placeholder-ish fields are dropped by the existing cleaning rule."""
    _spy(monkeypatch, {"longName": "NVIDIA Corporation",
                       "industry": placeholder,
                       "longBusinessSummary": placeholder})
    graph = _graph(tmp_path, monkeypatch, ScriptedModel(structured=True))

    identity = graph.create_run_state("NVDA", TODAY)["company_identity"]

    assert identity.get("company_name") == "NVIDIA Corporation"
    assert "industry" not in identity
    assert "business_description" not in identity


@pytest.mark.unit
def test_initialization_reuses_the_cached_profile_without_a_second_lookup(tmp_path, monkeypatch):
    """A direct context call followed by initialization reuses the cached profile:
    the vendor is asked once, and the context string is unchanged."""
    spy = _spy(monkeypatch, FULL_INFO)
    graph = _graph(tmp_path, monkeypatch, ScriptedModel(structured=True))

    direct = graph.resolve_instrument_context("NVDA", "stock", TODAY)
    state = graph.create_run_state("NVDA", TODAY)

    # The context path is preserved ...
    assert isinstance(direct, str) and "NVIDIA Corporation" in direct
    assert state["instrument_context"] == direct
    # ... and the second resolution reused the cache: exactly one vendor call.
    assert spy.calls == 1


# --------------------------------------------------------------------------- #
# Graph-state retention into final-state export, through both entry points
# --------------------------------------------------------------------------- #

@pytest.mark.unit
def test_the_retained_profile_survives_the_graph_and_reaches_save_reports(
    tmp_path, monkeypatch, offline,
):
    """A complete analysis retains the profile through the graph; save_reports writes
    it to both formats with exactly one lookup for the whole run."""
    spy = _spy(monkeypatch, FULL_INFO)
    graph = _graph(tmp_path, monkeypatch, ScriptedModel(structured=True))

    state, signal = graph.propagate("NVDA", TODAY)

    assert signal == state["final_rating"] == "Overweight"
    assert state.get("company_identity", {}).get("company_name") == "NVIDIA Corporation"

    markdown, page = _write_via_save_reports(graph, state)
    block = _background_markdown(markdown)
    assert "NVIDIA Corporation" in block
    assert "Semiconductors" in block
    assert DESCRIPTION_TWO in block
    html_block = _html_text(_background_html(page))
    assert "NVIDIA Corporation" in html_block
    assert "Semiconductors" in html_block
    assert DESCRIPTION_TWO in html_block
    # One lookup began the run; export added none.
    assert spy.calls == 1


@pytest.mark.unit
def test_the_retained_profile_reaches_the_cli_offer_reports_entry(
    tmp_path, monkeypatch, offline,
):
    """The CLI export entry writes files carrying the background in both formats."""
    spy = _spy(monkeypatch, FULL_INFO)
    graph = _graph(tmp_path, monkeypatch, ScriptedModel(structured=True))

    state, _signal = graph.propagate("NVDA", TODAY)

    markdown, page = _write_via_cli(tmp_path, state, graph, monkeypatch)
    block = _background_markdown(markdown)
    assert "NVIDIA Corporation" in block and "Semiconductors" in block
    html_block = _html_text(_background_html(page))
    assert "NVIDIA Corporation" in html_block and "Semiconductors" in html_block
    assert spy.calls == 1


@pytest.mark.unit
def test_a_run_without_the_fundamentals_analyst_still_carries_a_background(
    tmp_path, monkeypatch, offline,
):
    """The background does not depend on the Fundamentals Analyst."""
    _spy(monkeypatch, FULL_INFO)
    graph = _graph(tmp_path, monkeypatch, ScriptedModel(structured=True),
                   selected=("market", "news"))

    state, _signal = graph.propagate("NVDA", TODAY)

    assert "fundamentals" not in graph.selected_analysts
    markdown, page = _write_via_save_reports(graph, state)
    assert "NVIDIA Corporation" in _background_markdown(markdown)
    assert "NVIDIA Corporation" in _html_text(_background_html(page))


# --------------------------------------------------------------------------- #
# Persistence in the run log
# --------------------------------------------------------------------------- #

@pytest.mark.unit
def test_the_run_log_persists_company_identity(tmp_path):
    """The saved state log records the retained profile for later export/audit."""
    graph = object.__new__(trading_graph.TradingAgentsGraph)
    graph.config = {"results_dir": str(tmp_path / "logs")}
    graph.selected_analysts = ("market",)
    graph.run_settings = lambda: {}

    state = _export_state(company_identity={
        "company_name": "NVIDIA Corporation",
        "industry": "Semiconductors",
        "business_description": "GPU and networking maker.",
    })
    state.update(
        market_report="M", sentiment_report="", news_report="",
        fundamentals_report="", options_report="",
    )

    graph._log_state(state["trade_date"], state)

    log_file = next((tmp_path / "logs").rglob("full_states_log*.json"))
    logged = json.loads(log_file.read_text())
    assert logged["company_identity"] == state["company_identity"]


# --------------------------------------------------------------------------- #
# Presentation: exactly one section, placement, content (RPT-T1 / RPT-T2)
# --------------------------------------------------------------------------- #

@pytest.mark.unit
def test_exactly_one_background_sits_after_the_header_and_before_analysts(tmp_path, monkeypatch, offline):
    """RPT-T1 placement: one section, after the header, before the numbered sections,
    in both Markdown and HTML."""
    graph = _graph(tmp_path, monkeypatch, ScriptedModel(structured=True))
    state = _export_state(company_identity={
        "company_name": "NVIDIA Corporation",
        "industry": "Semiconductors",
        "business_description": DESCRIPTION_TWO,
    })

    markdown, page = _write_via_save_reports(graph, state)

    sections = _markdown_sections(markdown)
    assert list(sections).count("Company Background") == 1
    headings = list(sections)
    assert headings.index("Company Background") == 0          # first section after the header
    assert headings.index("I. Analyst Team Reports") > headings.index("Company Background")
    assert markdown.index("# Trading Analysis Report") < markdown.index("## Company Background")

    # HTML: one block, ahead of the first numbered analyst section.
    _background_html(page)                                     # asserts exactly one
    assert page.index("Company Background") < page.index("Analyst Team Reports")


@pytest.mark.unit
def test_full_profile_shows_name_industry_and_complete_description(tmp_path, monkeypatch, offline):
    """RPT-T1 content: all three fields, with the complete source description, both formats."""
    graph = _graph(tmp_path, monkeypatch, ScriptedModel(structured=True))
    state = _export_state(company_identity={
        "company_name": "NVIDIA Corporation",
        "industry": "Semiconductors",
        "business_description": DESCRIPTION_TWO,
    })

    markdown, page = _write_via_save_reports(graph, state)

    md_block = _background_markdown(markdown)
    for label in ("Name", "Industry"):
        assert label in md_block
    assert "NVIDIA Corporation" in md_block
    assert "Semiconductors" in md_block
    assert DESCRIPTION_TWO in md_block

    html_block = _html_text(_background_html(page))
    for label in ("Name", "Industry"):
        assert label in html_block
    assert "NVIDIA Corporation" in html_block
    assert "Semiconductors" in html_block
    assert DESCRIPTION_TWO in html_block


@pytest.mark.unit
def test_name_only_profile_omits_missing_labels_and_content(tmp_path, monkeypatch, offline):
    """RPT-T2: a name alone is shown; Industry/description labels and content omitted."""
    graph = _graph(tmp_path, monkeypatch, ScriptedModel(structured=True))
    state = _export_state(company_identity={"company_name": "NVIDIA Corporation"})

    markdown, page = _write_via_save_reports(graph, state)

    md_block = _background_markdown(markdown)
    assert "NVIDIA Corporation" in md_block
    assert "Industry" not in md_block
    assert "Semiconductors" not in md_block
    assert "graphics and compute" not in md_block
    assert "The final decision stands." in markdown

    html_block = _html_text(_background_html(page))
    assert "NVIDIA Corporation" in html_block
    assert "Industry" not in html_block
    assert "Semiconductors" not in html_block


# --------------------------------------------------------------------------- #
# Historical policy (RPT-T4) and missing data (RPT-T3)
# --------------------------------------------------------------------------- #

@pytest.mark.unit
def test_a_historical_run_labels_the_current_name_and_hides_undated_details(tmp_path, monkeypatch, offline):
    """RPT-T4: the current name is labelled current; industry and business are
    omitted in both Markdown and HTML."""
    graph = _graph(tmp_path, monkeypatch, ScriptedModel(structured=True))
    state = _export_state(
        trade_date=PAST,
        company_identity={
            "company_name": "NVIDIA Corporation",
            "industry": "Semiconductors",
            "business_description": DESCRIPTION_TWO,
        },
    )

    markdown, page = _write_via_save_reports(graph, state)

    md_block = _background_markdown(markdown)
    assert "NVIDIA Corporation" in md_block
    assert "current" in md_block.lower()             # explicitly labelled current
    assert "Semiconductors" not in md_block
    assert DESCRIPTION_TWO not in md_block

    html_block = _html_text(_background_html(page))
    assert "NVIDIA Corporation" in html_block
    assert "current" in html_block.lower()
    assert "Semiconductors" not in html_block
    assert DESCRIPTION_TWO not in html_block


@pytest.mark.unit
def test_a_historical_run_without_a_name_shows_the_notice_and_leaks_no_undated_fields(
    tmp_path, monkeypatch, offline,
):
    """Historical profile with only industry/description: unavailable notice; neither
    undated field appears in either format."""
    graph = _graph(tmp_path, monkeypatch, ScriptedModel(structured=True))
    state = _export_state(
        trade_date=PAST,
        company_identity={
            "industry": "Semiconductors",
            "business_description": DESCRIPTION_TWO,
        },
    )

    markdown, page = _write_via_save_reports(graph, state)

    md_block = _background_markdown(markdown)
    assert "unavailable" in md_block.lower() or "no company" in md_block.lower()
    assert "Semiconductors" not in md_block
    assert DESCRIPTION_TWO not in md_block
    assert "The final decision stands." in markdown

    html_block = _html_text(_background_html(page))
    assert "unavailable" in html_block.lower() or "no company" in html_block.lower()
    assert "Semiconductors" not in html_block
    assert DESCRIPTION_TWO not in html_block


@pytest.mark.unit
@pytest.mark.parametrize("identity", [None, {}])
def test_no_profile_shows_an_unavailable_notice_and_still_exports(
    tmp_path, monkeypatch, offline, identity,
):
    """RPT-T3: absent or empty profile yields the notice; the report completes,
    in both formats."""
    graph = _graph(tmp_path, monkeypatch, ScriptedModel(structured=True))
    overrides = {"company_identity": identity} if identity is not None else {}
    state = _export_state(**overrides)

    markdown, page = _write_via_save_reports(graph, state)

    md_block = _background_markdown(markdown)
    assert "unavailable" in md_block.lower() or "no company" in md_block.lower()
    assert "The final decision stands." in markdown
    assert "MARKET REPORT BODY" in markdown

    html_block = _html_text(_background_html(page))
    assert "unavailable" in html_block.lower() or "no company" in html_block.lower()
    assert "The final decision stands." in page


@pytest.mark.unit
def test_old_state_without_company_identity_exports_without_lookup_or_cache(tmp_path, monkeypatch, offline):
    """Old states stay readable: export uses only stored data; no lookup, no cache."""
    _forbid_lookups(monkeypatch)
    graph = _graph(tmp_path, monkeypatch, ScriptedModel(structured=True))
    state = _export_state()                       # no company_identity

    markdown, page = _write_via_save_reports(graph, state)

    md_block = _background_markdown(markdown)
    assert "unavailable" in md_block.lower() or "no company" in md_block.lower()
    assert "The final decision stands." in markdown
    assert "unavailable" in _html_text(_background_html(page)).lower() or \
        "no company" in _html_text(_background_html(page)).lower()


@pytest.mark.unit
def test_export_performs_no_additional_lookup_even_when_identity_is_present(tmp_path, monkeypatch, offline):
    """A present profile is read from the state; export makes no lookup."""
    _forbid_lookups(monkeypatch)
    graph = _graph(tmp_path, monkeypatch, ScriptedModel(structured=True))
    state = _export_state(
        company_identity={"company_name": "NVIDIA Corporation", "industry": "Semiconductors"}
    )

    markdown, page = _write_via_save_reports(graph, state)

    assert "NVIDIA Corporation" in _background_markdown(markdown)
    assert "NVIDIA Corporation" in _html_text(_background_html(page))


# --------------------------------------------------------------------------- #
# Business-description sentence handling (no model summarisation)
# --------------------------------------------------------------------------- #

@pytest.mark.unit
@pytest.mark.parametrize("summary, kept, dropped", [
    ("NVIDIA makes GPUs. It also sells networking gear.",
     ["NVIDIA makes GPUs.", "It also sells networking gear."], None),
    ("NVIDIA makes GPUs for many markets.",
     ["NVIDIA makes GPUs for many markets."], None),
    ("First sentence. Second sentence. Third sentence.",
     ["First sentence.", "Second sentence."], "Third sentence."),
    ("Margins held at 3.5 percent this quarter. Guidance was raised.",
     ["Margins held at 3.5 percent this quarter.", "Guidance was raised."], None),
    ("Results were strong. Revenue rose.",
     ["Results were strong.", "Revenue rose."], None),
])
def test_business_description_keeps_one_or_two_complete_source_sentences(
    tmp_path, monkeypatch, offline, summary, kept, dropped,
):
    """The description shows one or two complete source sentences, unsummarised,
    in both Markdown and HTML."""
    graph = _graph(tmp_path, monkeypatch, ScriptedModel(structured=True))
    state = _export_state(
        company_identity={"company_name": "NVIDIA Corporation", "business_description": summary}
    )

    markdown, page = _write_via_save_reports(graph, state)

    md_block = _background_markdown(markdown)
    html_block = _html_text(_background_html(page))
    for sentence in kept:
        assert sentence in md_block, f"Markdown missing {sentence!r}"
        assert sentence in html_block, f"HTML missing {sentence!r}"
    if dropped is not None:
        assert dropped not in md_block
        assert dropped not in html_block


@pytest.mark.unit
def test_the_description_is_not_truncated_mid_sentence(tmp_path, monkeypatch, offline):
    """A long first sentence is preserved whole (no arbitrary character cap)."""
    graph = _graph(tmp_path, monkeypatch, ScriptedModel(structured=True))
    long_first = "The company designs " + ("advanced computing platforms " * 40).strip() + "."
    summary = long_first + " Traders should read the full text."
    state = _export_state(
        company_identity={"company_name": "NVIDIA Corporation", "business_description": summary}
    )

    markdown, page = _write_via_save_reports(graph, state)

    md_block = _background_markdown(markdown)
    html_block = _html_text(_background_html(page))
    for block in (md_block, html_block):
        assert long_first in block
        assert "Traders should read the full text." in block


# --------------------------------------------------------------------------- #
# Format parity: literal source text, not rendered markup, in both formats
# --------------------------------------------------------------------------- #

@pytest.mark.unit
@pytest.mark.parametrize("name", [
    "Example *Group*",                 # Markdown emphasis markers
    "A&B <Holdings> Inc.",             # HTML-sensitive characters
    "Test _Co_ & <b>x</b> [link](y)",  # emphasis, entities and a link-shaped aside
])
def test_literal_profile_text_is_shown_the_same_way_in_both_formats(
    tmp_path, monkeypatch, offline, name,
):
    """The same visible source text appears in Markdown and HTML.

    The profile is source text, not markup: formatting characters a reader would
    see literally (``*Group*``, ``<b>``, ``[x](y)``) must not become emphasis,
    tags or links in the Markdown, and HTML must show the same literal characters.
    Both formats are compared on their visible text, so a reader sees one thing.
    """
    graph = _graph(tmp_path, monkeypatch, ScriptedModel(structured=True))
    state = _export_state(company_identity={
        "company_name": name,
        "industry": "Software & Services",
        "business_description": "Makes <widgets> and *tools*. Sold as [x](y).",
    })

    markdown, page = _write_via_save_reports(graph, state)

    md_visible = _md_visible_text(_background_markdown(markdown))
    html_visible = _html_text(_background_html(page))

    # The literal characters are what the reader sees, in both formats.
    assert name in md_visible, md_visible
    assert name in html_visible, html_visible
    # Markup did not take over: no emphasis/tags/links introduced from the text.
    md_body_html = MarkdownIt("commonmark", {"html": False}).render(_background_markdown(markdown))
    assert "<em>" not in md_body_html and "<strong>" not in md_body_html
    assert "<b>" not in md_body_html and "<a " not in md_body_html


# --------------------------------------------------------------------------- #
# Optional state field and legacy-state export
# --------------------------------------------------------------------------- #

@pytest.mark.unit
def test_company_identity_is_an_optional_state_field():
    """company_identity is optional in the state schema, not required."""
    from tradingagents.agents.state import AgentState

    assert "company_identity" in getattr(AgentState, "__optional_keys__", set())
    assert "company_identity" not in getattr(AgentState, "__required_keys__", set())


@pytest.mark.unit
def test_legacy_state_without_company_identity_still_exports(tmp_path, monkeypatch, offline):
    """A state built without company_identity (old runs) exports with the notice,
    and the graph still starts a fresh run that retains the field."""
    graph = _graph(tmp_path, monkeypatch, ScriptedModel(structured=True))

    # A legacy final state: no company_identity key at all.
    legacy = _export_state()
    legacy.pop("company_identity", None)
    markdown, page = _write_via_save_reports(graph, legacy)
    md_block = _background_markdown(markdown).lower()
    assert "unavailable" in md_block or "no company" in md_block
    html_block = _html_text(_background_html(page)).lower()
    assert "unavailable" in html_block or "no company" in html_block

    # The graph still initialises a fresh run whose state carries the field.
    _spy(monkeypatch, FULL_INFO)
    fresh = graph.create_run_state("NVDA", TODAY)
    assert "company_identity" in fresh


# --------------------------------------------------------------------------- #
# Custom resolve_instrument_context is respected during initialization
# --------------------------------------------------------------------------- #

@pytest.mark.unit
def test_initialization_respects_a_custom_resolve_instrument_context(tmp_path, monkeypatch):
    """An overridden resolve_instrument_context supplies the run's context string
    (the existing extension hook), while the profile is still retained from the
    one vendor lookup — no extra lookup, and the hook is actually used."""
    spy = _spy(monkeypatch, FULL_INFO)
    graph = _graph(tmp_path, monkeypatch, ScriptedModel(structured=True))

    calls = []

    def _custom_context(ticker, asset_type="stock", trade_date=None):
        calls.append((ticker, asset_type, trade_date))
        return "CUSTOM CONTEXT for " + str(ticker)

    graph.resolve_instrument_context = _custom_context

    state = graph.create_run_state("NVDA", TODAY)

    # The extension hook is used and its result reaches the run.
    assert calls == [("NVDA", "stock", TODAY)]
    assert state["instrument_context"] == "CUSTOM CONTEXT for NVDA"
    # The profile is still retained from exactly one vendor lookup and does not
    # depend on the custom context string.
    assert spy.calls == 1
    assert state["company_identity"]["company_name"] == "NVIDIA Corporation"

