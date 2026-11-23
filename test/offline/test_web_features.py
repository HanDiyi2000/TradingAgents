"""FEAT-01..FEAT-05 as the web shows them, using this repo's real formats.

Each case checks the *data source* the web view reuses and asserts what its
name says:

* FEAT-01 — the default analyst set the form offers includes the options analyst
  (from ``cli.prompts``), and its report reaches the run's content view.
* FEAT-02 — the early-stop reason appears in the activity **before** the manager
  plan, in that order.
* FEAT-03 — the final Markdown/HTML carry the Company Background section.
* FEAT-04 — after the first threshold crossing a later token usage still leaves
  exactly one web warning, and the analysis completes.
* FEAT-05 — real ``turn_citations`` records resolve a valid id to the numbered
  source paragraph, and invalid or uncited arguments keep their notice.

The exact HTML/JS rendering and browser interactions are acceptance items
recorded separately, not asserted here.
"""

from __future__ import annotations

import pytest

from cli.models import AnalystType, AssetType
from cli.prompts import filter_analysts_for_asset_type
from cli.web import RunManager
from tradingagents.agents.citations import (
    INVALID,
    UNCITED,
    build_report_paragraphs,
    resolve_turn,
)


class _Graph:
    def __init__(self, state, usage_totals=()):
        self._state = state
        self._usage_totals = usage_totals
        self.graph = self
        self.propagator = self
        self._resuming = False
        self.callbacks = []

    def create_run_state(self, ticker, trade_date, asset_type="stock", portfolio=None):
        return {"messages": [], "company_of_interest": ticker, "trade_date": trade_date}

    def get_graph_args(self, callbacks=None):
        self.callbacks = callbacks or []
        return {}

    def begin_checkpoint(self, *a, **k):
        return None

    def checkpoint_input(self, state):
        return state

    def end_checkpoint(self):
        pass

    def record_decision(self, *a, **k):
        pass

    def clear_checkpoint_on_success(self, *a, **k):
        pass

    def run_settings(self):
        return {"version": "test", "analysts": ["options"]}

    def save_reports(self, final_state, ticker, save_path=None, html=True):
        from tradingagents.reporting import write_report_tree

        return write_report_tree(final_state, ticker, save_path, settings=self.run_settings(), html=html)

    def stream_run(self, graph_input, **kwargs):
        # Post each configured usage through the real handler, as models would.
        for total in self._usage_totals:
            for handler in self.callbacks:
                _emit_usage(handler, total)
        yield [], {"market_report": self._state.get("market_report", "")}
        yield [], self._state


def _emit_usage(handler, total):
    """Post one model completion whose cumulative usage is ``total``."""
    from langchain_core.messages import AIMessage
    from langchain_core.outputs import ChatGeneration, LLMResult

    msg = AIMessage(content="x", usage_metadata={
        "input_tokens": total, "output_tokens": 0, "total_tokens": total})
    handler.on_llm_end(LLMResult(generations=[[ChatGeneration(message=msg)]]))


CONFIG = {"ticker": "NVDA", "analysis_date": "2026-11-22",
          "analysts": ["market", "options"], "asset_type": "stock"}


def _state(**overrides):
    base = {
        "company_of_interest": "NVDA",
        "trade_date": "2026-11-22",
        "company_identity": {"company_name": "NVIDIA", "industry": "Semiconductors",
                             "business_description": "Designs GPUs. Also sells software."},
        "market_report": "Market body.",
        "options_report": "First options paragraph.\n\nSecond options paragraph.",
        "investment_debate_state": {"bull_history": "", "bear_history": "",
                                    "report_paragraphs": [], "turn_citations": [],
                                    "progress_outcome": "", "progress_round": 0,
                                    "progress_reason": ""},
        "final_trade_decision": "Rating: Buy\n\nBuy NVDA.",
        "final_rating": "Buy",
    }
    base.update(overrides)
    return base


@pytest.mark.unit
def test_feat01_form_defaults_include_the_options_analyst():
    """FR-OPT-01: the default stock analyst set is the four plus options."""
    defaults = filter_analysts_for_asset_type(list(AnalystType), AssetType.STOCK)
    assert AnalystType.OPTIONS in defaults


@pytest.mark.unit
def test_feat02_the_stop_reason_appears_before_the_manager_plan():
    """FR-DEB-01: the recorded reason precedes the manager plan in the activity."""
    from tradingagents.agents.debate_progress import EARLY_STOP_REASON

    reason = _ai(f"Early stop: {EARLY_STOP_REASON}")
    plan = _ai("Research Manager plan: proceed cautiously.")
    state = _state(investment_debate_state={
        "bull_history": "Bull Analyst: x\n", "bear_history": "Bear Analyst: y\n",
        "report_paragraphs": [], "turn_citations": [],
        "progress_outcome": "NO_PROGRESS", "progress_round": 2,
        "progress_reason": EARLY_STOP_REASON,
    })

    graph = _Graph(state)
    # The graph yields the stop reason message, then the manager plan message.
    graph.stream_run = lambda graph_input, **kw: iter([
        ([reason], {"investment_debate_state": state["investment_debate_state"]}),
        ([plan], {"investment_plan": "proceed cautiously", "messages": []}),
        ([_ai("decision")], {"final_trade_decision": "Rating: Buy\n\nB.", "final_rating": "Buy"}),
    ])

    manager = RunManager(graph_factory=lambda *a, **k: graph, results_root=None)
    run_id = manager.start(CONFIG)
    manager.wait_until_done(run_id, timeout=5.0)

    events = manager.snapshot(run_id)["events"]
    texts = [str(e.get("text", "")) for e in events]
    reason_at = next(i for i, t in enumerate(texts) if EARLY_STOP_REASON in t)
    plan_at = next(i for i, t in enumerate(texts) if "proceed cautiously" in t)
    assert reason_at < plan_at, events


@pytest.mark.unit
def test_feat03_final_report_keeps_the_company_background():
    manager = RunManager(graph_factory=lambda *a, **k: _Graph(_state()), results_root=None)
    run_id = manager.start(CONFIG)
    manager.wait_until_done(run_id, timeout=5.0)

    result = manager.result(run_id)
    assert "Company Background" in result["markdown"]
    assert "Company Background" in result["html"]
    assert "NVIDIA" in result["markdown"]


@pytest.mark.unit
def test_feat04_one_token_warning_even_after_a_second_crossing():
    """FR-TOK-01: two oversized completions still yield exactly one warning."""
    from tradingagents.default_config import DEFAULT_TOKEN_WARNING_THRESHOLD

    over = DEFAULT_TOKEN_WARNING_THRESHOLD + 1
    state = _state()
    # First completion already exceeds; a second posts even more usage.
    graph = _Graph(state, usage_totals=(over, over + 5000))
    manager = RunManager(graph_factory=lambda *a, **k: graph, results_root=None)
    run_id = manager.start(CONFIG)
    manager.wait_until_done(run_id, timeout=5.0)

    snap = manager.snapshot(run_id)
    warnings = [e for e in snap["events"] if e.get("kind") == "token_warning"]
    assert len(warnings) == 1, warnings
    assert warnings[0]["total_tokens"] == over
    assert warnings[0]["threshold"] == DEFAULT_TOKEN_WARNING_THRESHOLD
    # The analysis continued to completion despite the warning.
    assert snap["state"] == "succeeded"


@pytest.mark.unit
def test_feat05_valid_citation_links_to_the_source_paragraph_text():
    """FR-CIT-01: a real recorded turn's [OPT-02] resolves to that paragraph's text."""
    reports = {"options_report": "First options paragraph.\n\nSecond options paragraph."}
    paragraphs = build_report_paragraphs(reports)
    assert [p["id"] for p in paragraphs] == ["OPT-01", "OPT-02"]

    entry = resolve_turn("bull", 1, "Demand is strong [OPT-02]", paragraphs)
    source_for = {p["id"]: p["text"] for p in paragraphs}

    # The recorded turn (real turn_citations shape) keeps the valid citation.
    valid = [c for arg in entry["arguments"] for c in arg["citations"] if c["valid"]]
    assert [c["id"] for c in valid] == ["OPT-02"]
    assert "".join(source_for[c["id"]] for c in valid) == "Second options paragraph."

    # What the run exports: the turn is recorded, the report is numbered with
    # the same ids, and the web preview anchors the id to that paragraph's text.
    state = _state(
        options_report=reports["options_report"],
        investment_debate_state={
            "bull_history": "Bull Analyst: Demand is strong [OPT-02]\n",
            "bear_history": "",
            "report_paragraphs": paragraphs,
            "turn_citations": [entry],
            "progress_outcome": "", "progress_round": 0, "progress_reason": "",
        },
    )
    manager = RunManager(graph_factory=lambda *a, **k: _Graph(state), results_root=None)
    run_id = manager.start(CONFIG)
    manager.wait_until_done(run_id, timeout=5.0)

    html = manager.result(run_id)["html"]
    # The valid citation is a link whose href targets the paragraph id...
    href_target = _href_for_text(html, "[OPT-02]")
    assert href_target == "para-OPT-02", html
    # ...and that target element carries the second paragraph's source text.
    assert _element_text_for_id(html, href_target) == "[OPT-02] Second options paragraph.", html
    # The numbered source paragraph and its text are present in the report.
    assert "[OPT-02] Second options paragraph." in manager.result(run_id)["markdown"]


@pytest.mark.unit
def test_feat05_invalid_and_missing_notices_are_visible_in_the_preview():
    """FR-CIT-01: an invalid and an uncited argument keep their notice in the preview."""
    paragraphs = build_report_paragraphs({"options_report": "Only paragraph."})
    invalid = resolve_turn("bull", 1, "Claim [OPT-99]", paragraphs)
    uncited = resolve_turn("bull", 2, "Claim with no reference", paragraphs)
    state = _state(
        options_report="Only paragraph.",
        investment_debate_state={
            "bull_history": "placeholder",
            "bear_history": "",
            "report_paragraphs": paragraphs,
            "turn_citations": [invalid, uncited],
            "progress_outcome": "", "progress_round": 0, "progress_reason": "",
        },
    )
    # The recorded bull history is what the exporter renders; build it from the
    # resolved turns so the preview carries exactly their notices.
    from tradingagents.agents.citations import render_annotated_turn

    state["investment_debate_state"]["bull_history"] = (
        "Bull Analyst: " + render_annotated_turn(invalid) + "\n\n" + render_annotated_turn(uncited))

    manager = RunManager(graph_factory=lambda *a, **k: _Graph(state), results_root=None)
    run_id = manager.start(CONFIG)
    manager.wait_until_done(run_id, timeout=5.0)

    html = manager.result(run_id)["html"]
    assert INVALID in html
    assert UNCITED in html


@pytest.mark.unit
def test_feat05_invalid_and_missing_citations_keep_their_notices():
    paragraphs = build_report_paragraphs({"options_report": "Only paragraph."})
    invalid = resolve_turn("bull", 1, "Claim [OPT-99]", paragraphs)
    uncited = resolve_turn("bull", 2, "Claim with no reference", paragraphs)

    invalid_notes = [arg["note"] for arg in invalid["arguments"]]
    uncited_notes = [arg["note"] for arg in uncited["arguments"]]
    assert INVALID in invalid_notes
    assert UNCITED in uncited_notes
    assert [c["valid"] for c in invalid["arguments"][0]["citations"]] == [False]


# --- message helpers -------------------------------------------------------------

def _ai(text):
    from langchain_core.messages import AIMessage

    return AIMessage(content=text)


def _parse_html(html):
    from html.parser import HTMLParser

    class _P(HTMLParser):
        def __init__(self):
            super().__init__()
            self.links = []   # (href, text)
            self.by_id = {}   # id -> text
            self._open_links = []
            self._open_ids = []

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "a" and attrs.get("href"):
                self._open_links.append([attrs["href"], ""])
            if attrs.get("id"):
                self.by_id[attrs["id"]] = ""
                self._open_ids.append(attrs["id"])

        def handle_endtag(self, tag):
            if tag == "a" and self._open_links:
                self.links.append(tuple(self._open_links.pop()))
            if tag in ("p", "div", "span", "li", "section", "h1", "h2", "h3", "h4") and self._open_ids:
                self._open_ids.pop()

        def handle_data(self, data):
            for link in self._open_links:
                link[1] += data
            for id_ in self._open_ids:
                self.by_id[id_] += data

    parser = _P()
    parser.feed(html)
    return parser


def _href_for_text(html, needle):
    """The href of the first link whose visible text contains ``needle``."""
    for href, text in _parse_html(html).links:
        if needle in text:
            return href.lstrip("#")
    return None


def _element_text_for_id(html, element_id):
    """The text inside the element with ``id=element_id`` (whitespace-collapsed)."""
    raw = _parse_html(html).by_id.get(element_id)
    return " ".join(raw.split()) if raw is not None else None
