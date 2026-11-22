"""FEAT-05 / FR-CIT-01: trace bull and bear arguments to numbered paragraphs.

Test-only patch. Nothing here is a pass, and no source code is changed to make
these tests pass: the module under test, ``tradingagents.agents.citations``, does
not exist yet. These tests fix the approved contract (revision 2 + revision 3
addendum + binding corrections) before implementation.

Proposed and approved *for test preparation*. They are not evidence until run
against an implementation.

Requirement: FR-CIT-01. Acceptance cases CIT-T1 through CIT-T9 as approved, with
the binding corrections:

1. CIT-T2 is exactly three prose paragraphs separated by explicit "\\n\\n".
2. Source-report segmentation is separate from debate-argument segmentation:
   source paragraphs follow blank lines (TextType "blocks"), skip headings and
   never split adjacent list items; debate arguments are markdown blocks, list
   items are separate arguments and indented continuation stays with its item.
3. The initial debate state omits ``report_paragraphs``; the map is built before
   the first researcher model call only when absent, and a present map (even
   ``{}``) is reused.

Nothing here is approved as done until the human reviews the test diff.
"""

from __future__ import annotations

import re
from unittest.mock import MagicMock

import pytest

from tradingagents.agents.debate_progress import PROGRESS
from tradingagents.graph.analyst_execution import ANALYST_NODE_SPECS
from tradingagents.graph.conditional_logic import ConditionalLogic
from tradingagents.graph.propagation import Propagator
from tradingagents.graph.setup import DEBATE_PATH_MAP, RISK_ANALYSIS_PATH_MAP

# Stable display constants (approved wording).
INVALID = "Invalid citation"
UNCITED = "No citation provided"

# Prefixes, one per supplied report.
PREFIX = {
    "market_report": "MKT",
    "sentiment_report": "SEN",
    "news_report": "NWS",
    "fundamentals_report": "FUN",
    "options_report": "OPT",
}

# --- stable identifiers (Revision 3 A1 / binding correction 1) --------------

FUNDAMENTALS = (
    "# Fundamentals\n"
    "\n"
    "Revenue grew 10% on strong demand.\n"
    "\n"
    "Gross margin held at 62%."
)

FUN_01 = "Revenue grew 10% on strong demand."
FUN_02 = "Gross margin held at 62%."

# CIT-T2: EXACTLY three prose paragraphs, separated by explicit "\n\n".
BEAR_TURN = (
    "Margins fell 2 points this quarter [FUN-01] [FUN-02] while volume rose."
    "\n\n"
    "The same crowding shows in options skew [FUN-99] on the front expiry."
    "\n\n"
    "The setup still favors caution into the print."
)

BEAR_ARG_1_TEXT = "Margins fell 2 points this quarter [FUN-01] [FUN-02] while volume rose."
BEAR_ARG_2_TEXT = "The same crowding shows in options skew [FUN-99] on the front expiry."
BEAR_ARG_3_TEXT = "The setup still favors caution into the print."

# The approved annotated form: each notice trails its own argument.
BEAR_ANNOTATED = (
    f"{BEAR_ARG_1_TEXT}\n"
    "\n"
    f"{BEAR_ARG_2_TEXT} — *{INVALID}: FUN-99.*\n"
    "\n"
    f"{BEAR_ARG_3_TEXT} — *{UNCITED}.*"
)

BULL_TURN = "Demand is intact for the next two quarters."

RISK_HISTORY = (
    "Aggressive Analyst: position sizing is fine.\n"
    "Conservative Analyst: volatility is a risk.\n"
    "Neutral Analyst: both sides have a point."
)


# --- helpers ----------------------------------------------------------------


def report_texts(exclude=(), **overrides):
    """The reports a run supplies, keyed by state field (the ``build_*`` input).

    ``exclude`` leaves an analyst unselected (its report is empty); ``overrides``
    replaces a report's text with ``<name>=`` (bare or with the ``_report``
    suffix). This is the one source of report text: the state and the expected
    paragraph map are both derived from it, so they cannot disagree.
    """
    texts = {key: f"Report for {key}." for key in PREFIX}
    # The approved fundamentals fixture, used both by the tests and by every
    # default run state, so a default fundamentals report always matches FUN-01/02.
    texts["fundamentals_report"] = FUNDAMENTALS
    for name, value in overrides.items():
        texts[_resolve(name)] = value
    for name in exclude:
        texts[_resolve(name)] = ""
    return texts


# The blueprint's source words, accepted alongside the state field names.
_SOURCE_NAME = {
    "market": "market_report", "sentiment": "sentiment_report",
    "news": "news_report", "fundamental": "fundamentals_report",
    "option": "options_report",
}


def _resolve(name):
    """The report state field for ``name`` (``fundamentals`` or ``fundamentals_report``)."""
    key = name if name.endswith("_report") else f"{name}_report"
    if key not in PREFIX:
        key = _SOURCE_NAME.get(name, "")
    assert key in PREFIX, f"unknown report {name!r}; use one of {sorted(PREFIX)}"
    return key


def expected_map(texts):
    """The map the approved numbering yields for ``texts`` (contrast fixture)."""
    paragraphs = []
    for key, prefix in PREFIX.items():
        token = prefix + "-"
        for n, paragraph in enumerate(_source_paragraphs(texts[key]), 1):
            paragraphs.append({
                "id": f"{token}{n:02d}",
                "source": prefix,
                "report_key": key,
                "text": paragraph,
            })
    return paragraphs


def report_map(exclude=(), **overrides):
    """The expected map for a run supplying ``report_texts(exclude, ...)``.

    An independent restatement of the approved numbering, so a wrong
    implementation of ``build_report_paragraphs`` cannot pass by agreeing with
    itself.
    """
    return expected_map(report_texts(exclude, **overrides))


def _source_paragraphs(text):
    """An independent restatement of the approved source segmentation.

    Blank-line blocks; a block that is only headings is skipped; a block whose
    first line is a one-line heading followed by body text contributes the body.
    """
    paragraphs = []
    for block in re.split(r"\n[ \t]*\n", text or ""):
        lines = [line for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        if re.fullmatch(r"#{1,6}\s.*", lines[0].strip()):
            if len(lines) == 1:
                continue  # a heading on its own gets no ID
            lines = lines[1:]  # one-line heading directly above body text
        body = "\n".join(lines)
        if body.strip() and not all(re.fullmatch(r"#{1,6}\s.*", line.strip()) for line in lines):
            paragraphs.append(body)
    return paragraphs


ABSENT = object()  # "the field is not in the state at all" (binding correction 3)

# The reports every test starts from, and the map they yield: the one pair a
# test may use without deriving it, since ``_state()`` defaults to these reports.
DEFAULT_TEXTS = report_texts()
DEFAULT_MAP = report_map()


def _state(texts=None, paragraphs=ABSENT, debate=None, **extra):
    """A stock run built from ``texts`` (a ``report_texts`` dict).

    The report fields are exactly ``texts``, so they always match whichever map
    the test supplies. ``paragraphs`` is what the debate state carries: left
    absent by default (the pre-FEAT-05 shape), or a map when given — including
    ``[]`` and ``{}``, which are present, initialized values.
    """
    base = {
        "company_of_interest": "NVDA",
        "asset_type": "stock",
        "trade_date": "2026-01-09",
        "instrument_context": "The instrument to analyze is `NVDA`.",
        "portfolio_context": "",
        "past_context": "",
        "investment_plan": "plan",
        "trader_investment_plan": "Trader plan.",
        "risk_debate_state": _risk_state(),
        "final_trade_decision": "**Rating**: Overweight",
    }
    base.update(report_texts() if texts is None else texts)
    for key, value in extra.items():
        base[key] = value
    discussion = {
        "bull_history": "",
        "bear_history": "",
        "history": "",
        "current_response": "",
        "count": 0,
    }
    discussion.update(debate or {})
    if paragraphs is not ABSENT:
        discussion["report_paragraphs"] = paragraphs
    base["investment_debate_state"] = discussion
    return base


def _risk_state():
    return {
        "aggressive_history": RISK_HISTORY,
        "conservative_history": RISK_HISTORY,
        "neutral_history": RISK_HISTORY,
        "history": RISK_HISTORY,
        "latest_speaker": "Neutral Analyst",
        "current_aggressive_response": RISK_HISTORY,
        "current_conservative_response": RISK_HISTORY,
        "current_neutral_response": RISK_HISTORY,
        "count": 3,
    }


class RecordingLLM:
    """A researcher/summary model that records every prompt it is handed."""

    def __init__(self, response=BULL_TURN):
        self.response = response
        self.prompts: list = []

    def invoke(self, prompt, *args, **kwargs):
        self.prompts.append(prompt)
        return MagicMock(content=self.response)

    def with_structured_output(self, *args, **kwargs):
        raise NotImplementedError

    @property
    def prompt_text(self) -> str:
        return "\n".join(_prompt_text(p) for p in self.prompts)


def _prompt_text(prompt) -> str:
    if isinstance(prompt, str):
        return prompt
    if isinstance(prompt, dict):
        return str(prompt.get("content", prompt))
    parts = []
    for item in prompt:
        content = getattr(item, "content", None)
        if content is None and isinstance(item, dict):
            content = item.get("content", "")
        parts.append(str(content))
    return "\n".join(parts)


def researcher_prompt(state):
    """The exact source text a bull/bear node hands its model."""
    from tradingagents.agents.researchers.bull_researcher import create_bull_researcher

    llm = RecordingLLM()
    create_bull_researcher(llm)(dict(state))
    return llm.prompt_text


def numbered_text(state, label):
    """The source text as it appears after the prompt label (``label``)."""
    prompt = researcher_prompt(state)
    _, _, tail = prompt.partition(label)
    return tail


def citations_of(entry):
    return [c["id"] for c in entry.get("citations", [])]


def entries_for(state):
    return state["investment_debate_state"]["turn_citations"]


# --- CIT-T1: numbering before the debate; both researchers; exports --------


@pytest.mark.unit
def test_cit_t1_both_researchers_see_the_same_labels_on_the_original_paragraphs():
    """CIT-T1 / FR-CIT-01: the labels are on the same original text for bull and
    bear, the heading has no ID, and the options report starts at OPT-01."""
    from tradingagents.agents.researchers.bear_researcher import create_bear_researcher
    from tradingagents.agents.researchers.bull_researcher import create_bull_researcher

    texts = report_texts(options="## Chain\n\nCalls are bid at 1.2.\n\nSpreads widened.")
    paragraphs = expected_map(texts)
    state = _state(texts, paragraphs)

    bull, bear = RecordingLLM(), RecordingLLM()
    create_bull_researcher(bull)(dict(state))
    create_bear_researcher(bear)(dict(state))

    said = "\n".join(_prompt_text(p) for p in bull.prompts + bear.prompts)
    assert f"[FUN-01] {FUN_01}" in said
    assert f"[FUN-02] {FUN_02}" in said
    assert "[FUN-01] # Fundamentals" not in said and "[FUN-00]" not in said
    assert "[OPT-01] Calls are bid at 1.2." in said

    ids = [p["id"] for p in paragraphs if p["report_key"] == "options_report"]
    assert ids == ["OPT-01", "OPT-02"]


@pytest.mark.unit
def test_cit_t1_options_only_run_still_numbers_from_opt_01():
    """CIT-T1 (repeat): an options-only selection numbers its report OPT-01."""
    texts = report_texts(
        exclude=("market", "sentiment", "news", "fundamentals"),
        options="## Chain\n\nCalls are bid at 1.2.",
    )
    state = _state(texts, expected_map(texts))

    said = researcher_prompt(state)
    assert "[OPT-01] Calls are bid at 1.2." in said
    assert "[MKT-01]" not in said and "[FUN-01]" not in said


@pytest.mark.unit
def test_cit_t1_a_deselected_analyst_is_not_numbered():
    """CIT-T1: an unselected analyst is not numbered and not invented.

    CIT-T6 calls this out separately; here it guards the numbering routine.
    """
    from tradingagents.agents.citations import build_report_paragraphs

    texts = report_texts(exclude=("market", "news", "options"), sentiment="Sentiment only.")
    paragraphs = build_report_paragraphs(dict(texts))

    assert {p["source"] for p in paragraphs} == {"SEN", "FUN"}
    assert ids_for_sources(paragraphs, "MKT") == []
    assert ids_for_sources(paragraphs, "OPT") == []
    assert ids_for_sources(paragraphs, "FUN") == ids_for_sources(expected_map(texts), "FUN")


def ids_for_sources(paragraphs, source):
    return [p["id"] for p in paragraphs if p["source"] == source]


# --- Binding correction 2: source vs debate segmentation -------------------


@pytest.mark.unit
def test_binding_c2_source_list_items_keep_one_id_per_blank_line_block():
    """Binding correction 2: source segmentation follows blank lines; adjacent
    list items are NOT split into separate IDs by their markers."""
    from tradingagents.agents.citations import build_report_paragraphs

    report = "- Margins fell 2 points.\n- Valuation is 40x."
    paragraphs = build_report_paragraphs({**dict.fromkeys(PREFIX, ""), "fundamentals_report": report})

    assert [p["id"] for p in paragraphs] == ["FUN-01"]
    assert paragraphs[0]["text"] == report


@pytest.mark.unit
def test_binding_c2_source_paragraphs_skip_headings_and_keep_body_text_after_one():
    """Binding correction 2 / Revision 3 A2: a heading gets no ID, and the body
    text after it is numbered, whether or not a blank line separates them."""
    from tradingagents.agents.citations import build_report_paragraphs

    report = "## Risks\nMargins fell.\n\n## Outlook\n\nDemand is steady."
    paragraphs = build_report_paragraphs({**dict.fromkeys(PREFIX, ""), "fundamentals_report": report})

    assert [p["id"] for p in paragraphs] == ["FUN-01", "FUN-02"]
    assert paragraphs[0]["text"].strip() == "Margins fell."
    assert paragraphs[1]["text"].strip() == "Demand is steady."


@pytest.mark.unit
def test_binding_c2_debate_list_items_are_separate_arguments():
    """Binding correction 2 / A2: inside a turn, each list item is its own
    argument, so each can carry its own citation and notice."""
    from tradingagents.agents.citations import split_arguments

    turn = (
        "- Margins fell 2 points [FUN-01]\n"
        "- Valuation is 40x [FUN-99]\n"
        "- Demand is opaque"
    )
    arguments = split_arguments(turn)

    assert [a.text for a in arguments] == [
        "- Margins fell 2 points [FUN-01]",
        "- Valuation is 40x [FUN-99]",
        "- Demand is opaque",
    ]


@pytest.mark.unit
def test_binding_c2_indented_continuation_stays_with_its_item():
    """Binding correction 2: an indented continuation line belongs to its item."""
    from tradingagents.agents.citations import split_arguments

    turn = "- Margins fell 2 points [FUN-01]\n  and volume rose with it.\n- Demand is opaque"
    arguments = split_arguments(turn)

    assert len(arguments) == 2
    assert "and volume rose with it." in arguments[0].text
    assert arguments[1].text == "- Demand is opaque"


@pytest.mark.unit
def test_binding_c2_a_table_is_one_argument_in_a_turn():
    """A2: a whole table is one argument (one evidence unit)."""
    from tradingagents.agents.citations import split_arguments

    turn = "Metric | Value\n---|---\nATM IV | 25%\nSpread | 0.2\n\nThe setup favors caution."
    arguments = split_arguments(turn)

    assert len(arguments) == 2
    assert "ATM IV | 25%" in arguments[0].text


@pytest.mark.unit
def test_binding_c2_one_fenced_code_rule_attaches_to_the_preceding_argument():
    """A2: one consistent rule — a fenced block is not an argument; it attaches in
    full to the argument that precedes it, or is its own leading argument."""
    from tradingagents.agents.citations import split_arguments

    assert [a.text for a in split_arguments("Claim [FUN-01].\n```\nclose=1.0\n```\n\nNext claim.")] == [
        "Claim [FUN-01].\n```\nclose=1.0\n```",
        "Next claim.",
    ]
    assert [a.text for a in split_arguments("```\nclose=1.0\n```\n\nNext claim.")] == [
        "```\nclose=1.0\n```",
        "Next claim.",
    ]


# --- CIT-T8: extraction only from the current argument ---------------------


@pytest.mark.unit
def test_cit_t8_the_run_map_never_adds_a_citation_the_model_did_not_write():
    """CIT-T8 / FR-CIT-01: an argument with no label is never given one just
    because the map holds a matching paragraph."""
    from tradingagents.agents.citations import resolve_turn

    turn = "Margins fell 2 points this quarter."
    paragraphs = DEFAULT_MAP  # pairs with _state()'s default reports
    entry = resolve_turn("bear", 1, turn, paragraphs)

    assert [citations_of(a) for a in entry["arguments"]] == [[]]
    assert entry["arguments"][0]["note"] == UNCITED


@pytest.mark.unit
def test_cit_t8_a_label_stays_in_the_argument_that_wrote_it():
    """CIT-T8: a label from one argument (or another turn) is not attributed to
    the current one, and its inline position is preserved."""
    from tradingagents.agents.citations import resolve_turn

    turn = "Margins fell [FUN-01].\n\nVolume rose."
    entry = resolve_turn("bear", 2, turn, report_map())

    first, second = entry["arguments"]
    assert citations_of(first) == ["FUN-01"]
    assert first["citations"][0]["position"] == first["text"].index("[FUN-01]")
    assert second["citations"] == []
    assert second["note"] == UNCITED


@pytest.mark.unit
def test_cit_t8_only_this_runs_map_decides_validity():
    """CIT-T8: the same label is invalid on a run whose map lacks it."""
    from tradingagents.agents.citations import resolve_turn

    paragraphs = [{"id": "MKT-01", "source": "MKT", "report_key": "market_report", "text": "m"}]
    entry = resolve_turn("bear", 1, "Demand is opaque [FUN-01].", paragraphs)

    citation = entry["arguments"][0]["citations"][0]
    assert citation["valid"] is False
    assert entry["arguments"][0]["note"] == INVALID


# --- CIT-T2: ONE turn, three prose paragraphs (binding correction 1) -------


@pytest.mark.unit
def test_cit_t2_one_turn_three_arguments_each_notice_beside_its_own_claim():
    """CIT-T2 / FR-CIT-01: exactly three prose paragraphs separated by explicit
    "\\n\\n"; [FUN-01] and [FUN-02] valid in argument 1 with no notice;
    [FUN-99] invalid in argument 2 only; no citation in argument 3 only."""
    from tradingagents.agents.citations import resolve_turn

    entry = resolve_turn("bear", 1, BEAR_TURN, report_map())

    assert [a["text"] for a in entry["arguments"]] == [
        BEAR_ARG_1_TEXT, BEAR_ARG_2_TEXT, BEAR_ARG_3_TEXT,
    ]
    one, two, three = entry["arguments"]

    assert citations_of(one) == ["FUN-01", "FUN-02"]
    assert all(c["valid"] for c in one["citations"])
    assert one["note"] == ""
    assert [c["position"] for c in one["citations"]] == sorted(
        c["position"] for c in one["citations"]
    )

    assert citations_of(two) == ["FUN-99"]
    assert two["citations"][0]["valid"] is False
    assert two["note"] == INVALID

    assert three["citations"] == []
    assert three["note"] == UNCITED


@pytest.mark.unit
def test_cit_t2_annotated_turn_matches_the_approved_text():
    """CIT-T2: the annotated turn keeps every original citation in place and
    appends each notice to its own argument only."""
    from tradingagents.agents.citations import render_annotated_turn, resolve_turn

    entry = resolve_turn("bear", 1, BEAR_TURN, report_map())

    rendered = render_annotated_turn(entry)
    assert rendered == BEAR_ANNOTATED
    for text in (BEAR_ARG_1_TEXT, BEAR_ARG_2_TEXT, BEAR_ARG_3_TEXT):
        assert rendered.count(text) == 1
    assert rendered.count(INVALID) == 1
    assert rendered.count(UNCITED) == 1


@pytest.mark.unit
def test_cit_t2_the_bear_node_records_the_annotated_turn_and_its_citations():
    """CIT-T2: the real bear node writes the annotated turn into history and its
    argument-level citations into the debate state.

    The record is found by its raw text, not by an ordinal: the turn number is
    the bear's own dialogue count, which this test does not constrain (FR-CIT-01
    says nothing about how a turn is numbered)."""
    from tradingagents.agents.researchers.bear_researcher import create_bear_researcher

    paragraphs = DEFAULT_MAP  # pairs with _state()'s default reports
    bull_turn = "Bull Analyst: Demand is intact."
    state = _state(paragraphs=paragraphs, debate={
        "history": bull_turn, "bull_history": bull_turn,
        "current_response": bull_turn, "count": 1,
    })

    node = create_bear_researcher(RecordingLLM(BEAR_TURN))
    update = node(state)
    debate = update["investment_debate_state"]

    assert debate["history"] == bull_turn + "\n" + "Bear Analyst: " + BEAR_ANNOTATED
    assert debate["bear_history"] == "\n" + "Bear Analyst: " + BEAR_ANNOTATED
    assert debate["current_response"] == "Bear Analyst: " + BEAR_ANNOTATED

    entries = entries_for(update)
    bear_entries = [e for e in entries if e["speaker"] == "bear"]
    assert len(bear_entries) == 1, "one record per bear turn"
    entry = bear_entries[0]
    assert entry["raw"] == BEAR_TURN, "the record keeps the model's own text"
    assert [citations_of(a) for a in entry["arguments"]] == [
        ["FUN-01", "FUN-02"], ["FUN-99"], [],
    ]
    assert [a["note"] for a in entry["arguments"]] == ["", INVALID, UNCITED]


@pytest.mark.unit
def test_cit_t2_the_research_manager_reads_each_notice_beside_its_own_claim():
    """CIT-T2: the manager reads the history the real bear node recorded — not
    a hand-written copy — so the three associations reach its own prompt, and
    the manager passes that recorded history through unchanged."""
    from tradingagents.agents.managers.research_manager import create_research_manager
    from tradingagents.agents.researchers.bear_researcher import create_bear_researcher
    from tradingagents.agents.schemas import ResearchPlan, render_research_plan

    paragraphs = DEFAULT_MAP  # pairs with _state()'s default reports
    bull_turn = "Bull Analyst: Demand is intact."
    before = _state(paragraphs=paragraphs, debate={
        "history": bull_turn, "bull_history": bull_turn,
        "current_response": bull_turn, "count": 1,
    })
    recorded = create_bear_researcher(RecordingLLM(BEAR_TURN))(before)
    history = recorded["investment_debate_state"]["history"]
    assert history.endswith("Bear Analyst: " + BEAR_ANNOTATED)

    after = _state(paragraphs=paragraphs, debate=recorded["investment_debate_state"])

    captured = _Structured(
        ResearchPlan(recommendation="Overweight", rationale="r", strategic_actions="a"),
        render_research_plan,
    )
    llm = RecordingLLM("unused: the structured call answers")
    llm.with_structured_output = lambda *a, **k: captured
    plan = create_research_manager(llm)(after)

    assert len(captured.prompts) == 1, "the manager must call its model once"
    prompt = captured.prompts[0]
    assert history in prompt
    assert BEAR_ANNOTATED in prompt
    assert prompt.count(INVALID) == 1 and prompt.count(UNCITED) == 1
    # The valid pair keeps both IDs, in place, and takes no notice.
    assert "[FUN-01] [FUN-02]" in prompt
    assert f"{BEAR_ARG_1_TEXT} —" not in prompt
    # Each notice trails its own claim inside the manager's prompt.
    assert f"{BEAR_ARG_2_TEXT} — *{INVALID}: FUN-99.*" in prompt
    assert f"{BEAR_ARG_3_TEXT} — *{UNCITED}.*" in prompt

    assert plan["investment_plan"].strip()
    assert plan["investment_debate_state"]["history"] == history
    # The manager carries the citation record onward without importing the leaf:
    # it copies the fields from the state it was handed.
    assert (plan["investment_debate_state"]["turn_citations"]
            == after["investment_debate_state"]["turn_citations"])
    assert (plan["investment_debate_state"]["report_paragraphs"]
            == after["investment_debate_state"]["report_paragraphs"])


class _Structured:
    """The manager's structured-output stand-in; it records every prompt."""

    def __init__(self, result, render):
        self.result, self.render = result, render
        self.prompts: list = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return self.result


@pytest.mark.unit
def test_cit_t2_the_debate_continues_after_invalid_and_uncited_arguments():
    """CIT-T2: neither an invalid nor an uncited argument stops or diverts the
    debate (FR-CIT-01 'continue the debate in both cases')."""
    # Cap 3: after the opening pair (count 2) the debate has room to continue.
    logic = ConditionalLogic(max_debate_rounds=3)

    debate = {
        "history": "Bear Analyst: " + BEAR_ANNOTATED,
        "bull_history": "\nBull Analyst: Demand is intact.",
        "bear_history": "\nBear Analyst: " + BEAR_ANNOTATED,
        "current_response": "Bear Analyst: " + BEAR_ANNOTATED,
        "count": 2,
    }
    settled = _state(debate=debate)
    # The bear spoke last in a completed pair: the bull answers next.
    assert logic.should_continue_debate(settled) == "Bull Researcher"
    # Both notices are present in the history that drives that decision.
    assert INVALID in debate["current_response"]
    assert UNCITED in debate["current_response"]


# --- CIT-T3: FEAT-02 interaction, routing untouched -----------------------


def set_debate_cap(cap):
    """Set ``max_debate_rounds`` in the run config the bear node reads (FEAT-02).

    ``test/conftest.py`` already isolates the global config per test, so this
    needs no restore of its own; it is called only by the cases that judge a
    pair, where the cap decides whether a judgement is scheduled at all.
    """
    from tradingagents.dataflows import config as config_module

    config_module.set_config({**config_module.get_config(), "max_debate_rounds": cap})


def _judge_returning(outcome):
    """A judge as FEAT-02 calls it: ``judge.invoke(prompt)`` → ``ProgressResult``."""
    from tradingagents.agents.debate_progress import ProgressResult

    seen = []

    class _Judge:
        def invoke(self, prompt):
            seen.append(prompt)
            return ProgressResult(outcome, 2)

    _Judge.seen = seen
    return _Judge()


def _bear_pair_state(paragraphs):
    """A counted first round: bull spoken, bear about to answer (count 3)."""
    bull_turn = "Bull Analyst: Revenue grew 10% [FUN-01]."
    return bull_turn, _state(paragraphs=paragraphs, debate={
        "history": bull_turn,
        "bull_history": "\n" + bull_turn,
        "bear_history": "\nBear Analyst: earlier.",
        "current_response": bull_turn,
        "count": 3,
    })


@pytest.mark.unit
def test_cit_t3_a_first_reply_may_reuse_the_same_paragraph_and_progress():
    """CIT-T3 / FR-DEB-01+FR-CIT-01: the bear's first reply citing the bull's
    paragraph resolves to that paragraph, its PROGRESS judgement is recorded,
    and the router sends the debate on to the bull."""
    from tradingagents.agents.citations import resolve_turn

    from tradingagents.agents.researchers.bear_researcher import create_bear_researcher

    paragraphs = DEFAULT_MAP  # pairs with _state()'s default reports
    claim = "That 10% came from one customer [FUN-01], which is concentration risk."
    bull_turn = "Bull Analyst: Revenue grew 10% [FUN-01]."

    for speaker, text in (("bull", bull_turn), ("bear", claim)):
        entry = resolve_turn(speaker, 2, text, paragraphs)
        assert citations_of(entry["arguments"][0]) == ["FUN-01"], speaker
        assert entry["arguments"][0]["citations"][0]["valid"] is True, speaker
        assert entry["arguments"][0]["note"] == "", speaker

    _, state = _bear_pair_state(paragraphs)
    set_debate_cap(3)  # round 2 sits below the cap, so the pair is judged
    judge = _judge_returning(PROGRESS)
    debate = create_bear_researcher(
        RecordingLLM("Bear Analyst: " + claim), judge=judge,
    )(state)["investment_debate_state"]

    assert debate["count"] == 4
    assert debate["progress_outcome"] == PROGRESS
    assert debate["progress_round"] == 2
    assert debate["progress_reason"] == ""

    # Routing after a PROGRESS pair: the debate continues with the bull.
    assert debate["current_response"].startswith("Bear Analyst:")
    router = ConditionalLogic(max_debate_rounds=3)
    assert router.should_continue_debate({**state, "investment_debate_state": debate}) == "Bull Researcher"


@pytest.mark.unit
def test_cit_t3_the_judge_receives_the_recorded_annotated_turns_and_its_judgement():
    """CIT-T3: FEAT-05 adds no routing input. The FEAT-02 judge still sees the
    recorded turns — annotated, notices included, exactly as they are written to
    history — and its judgement, not the citations, is what the router acts on.

    The judge reading raw, un-annotated text instead would be a design change to
    FEAT-02 and is not part of the approved contract.
    """
    from tradingagents.agents.researchers.bear_researcher import create_bear_researcher

    paragraphs = DEFAULT_MAP  # pairs with _state()'s default reports
    bull_turn, state = _bear_pair_state(paragraphs)
    set_debate_cap(3)  # round 2 sits below the cap, so the pair is judged
    judge = _judge_returning(PROGRESS)
    raw = "Bear Analyst: Demand is opaque."

    update = create_bear_researcher(RecordingLLM(raw), judge=judge)(state)
    debate = update["investment_debate_state"]

    assert len(judge.seen) == 1, "one judgement per completed pair"
    prompt = judge.seen[0]
    # The bull's recorded turn cites a valid paragraph, so it is written to
    # history unchanged and takes no notice; the judge sees it exactly so.
    assert bull_turn in prompt, "the bull's recorded turn reaches the judge"
    assert f"{bull_turn} \u2014 *{UNCITED}.*" not in prompt, (
        "a valid bull citation must not be marked uncited")
    assert f"{bull_turn} \u2014 *{INVALID}" not in prompt, (
        "a valid bull citation must not be marked invalid")
    # The bear's turn reaches the judge exactly as it is recorded — the same
    # annotated text the router reads and the manager is handed — and the bear
    # wrote no ID, so its recorded turn carries the uncited notice.
    assert debate["current_response"] in prompt, "the bear's recorded turn reaches the judge"
    assert UNCITED in debate["current_response"], "the uncited bear argument is recorded as such"

    # Same recorded debate, a NO_PROGRESS judgement: the router stops. Citations
    # never override the judgement.
    stopped = dict(debate, progress_outcome="NO_PROGRESS")
    router = ConditionalLogic(max_debate_rounds=3)
    assert router.should_continue_debate(
        {**state, "investment_debate_state": stopped}) == "Research Manager"
    assert router.should_continue_debate(
        {**state, "investment_debate_state": debate}) == "Bull Researcher"


# --- Binding correction 3: map built only when absent ---------------------


@pytest.mark.unit
def test_binding_c3_the_initial_debate_state_omits_report_paragraphs():
    """Binding correction 3: initialization must not pre-carve the field, so a
    fresh run and an empty run are distinguishable."""
    initial = Propagator().create_initial_state("NVDA", "2026-01-09")

    assert "report_paragraphs" not in initial["investment_debate_state"]


@pytest.mark.unit
def test_binding_c3_the_map_is_built_before_the_first_researcher_model_call():
    """Binding correction 3: with the field absent, the first researcher's model
    call already carries the labels, and the node stores that same map."""
    from tradingagents.agents.researchers.bull_researcher import create_bull_researcher

    paragraphs = DEFAULT_MAP  # pairs with _state()'s default reports
    llm = RecordingLLM()
    state = _state(debate={"count": 0})
    assert "report_paragraphs" not in state["investment_debate_state"]

    update = create_bull_researcher(llm)(state)

    assert len(llm.prompts) == 1
    prompt = _prompt_text(llm.prompts[0])
    assert f"[FUN-01] {FUN_01}" in prompt
    assert f"[FUN-02] {FUN_02}" in prompt
    assert "[MKT-01]" in prompt and "[NWS-01]" in prompt
    assert update["investment_debate_state"]["report_paragraphs"] == paragraphs


@pytest.mark.unit
def test_binding_c3_a_present_map_is_reused_verbatim_including_an_empty_one():
    """Binding correction 3: a present map is never rebuilt or renumbered. The
    same contract for every present value: ``[]``, ``{}`` and a non-empty map
    are each stored and used as given."""
    from tradingagents.agents.researchers.bull_researcher import create_bull_researcher

    for present in ([], {}, report_map()):
        llm = RecordingLLM()
        update = create_bull_researcher(llm)(_state(paragraphs=present, debate={"count": 0}))
        stored = update["investment_debate_state"]["report_paragraphs"]
        assert stored == present, present
        if present:  # a non-empty map labels the prompt
            assert "[FUN-01]" in _prompt_text(llm.prompts[0])

    # An empty map is not repopulated from the reports on a later turn either.
    empty = _state(paragraphs={}, debate={
        "count": 1, "current_response": "Bull Analyst: Demand is intact.",
    })
    llm = RecordingLLM()
    from tradingagents.agents.researchers.bear_researcher import create_bear_researcher

    update = create_bear_researcher(llm)(empty)
    assert update["investment_debate_state"]["report_paragraphs"] == {}
    assert "[FUN-01]" not in _prompt_text(llm.prompts[0])


@pytest.mark.unit
def test_binding_c3_the_bear_reuses_the_bulls_map_without_rebuilding():
    """Binding correction 3: the second researcher reads the map the bull
    stored, and does not renumber its own copy."""
    from tradingagents.agents.researchers.bear_researcher import create_bear_researcher
    from tradingagents.agents.researchers.bull_researcher import create_bull_researcher

    bull_update = create_bull_researcher(RecordingLLM())(_state(debate={"count": 0}))
    debate = bull_update["investment_debate_state"]
    debate["count"] = 1
    debate["current_response"] = "Bull Analyst: Demand is intact."
    stored = debate["report_paragraphs"]

    llm = RecordingLLM()
    bear_update = create_bear_researcher(llm)(_state(paragraphs=stored, debate=debate))

    assert bear_update["investment_debate_state"]["report_paragraphs"] == stored
    prompt = _prompt_text(llm.prompts[0])
    assert f"[FUN-01] {FUN_01}" in prompt


# --- CIT-T4: stability across researchers, repeats and re-export ----------


@pytest.mark.unit
def test_cit_t4_identical_labels_for_both_researchers():
    """CIT-T4: the bull and the bear are handed the same labels."""
    from tradingagents.agents.researchers.bear_researcher import create_bear_researcher
    from tradingagents.agents.researchers.bull_researcher import create_bull_researcher

    paragraphs = DEFAULT_MAP  # pairs with _state()'s default reports
    bull = RecordingLLM()
    create_bull_researcher(bull)(_state(paragraphs=paragraphs, debate={"count": 0}))
    bear = RecordingLLM()
    create_bear_researcher(bear)(_state(
        paragraphs=paragraphs,
        debate={"count": 1, "current_response": "Bull Analyst: x"},
    ))

    for id_ in ("[FUN-01]", "[FUN-02]", "[MKT-01]", "[NWS-01]"):
        assert id_ in _prompt_text(bull.prompts[0]), id_
        assert id_ in _prompt_text(bear.prompts[0]), id_


@pytest.mark.unit
def test_cit_t4_reprocessing_the_same_reports_yields_the_same_ids():
    """CIT-T4: numbering is a pure function of the reports."""
    from tradingagents.agents.citations import build_report_paragraphs

    reports = {"market_report": "m", "sentiment_report": "", "news_report": "n",
               "fundamentals_report": FUNDAMENTALS, "options_report": "o"}
    first = build_report_paragraphs(dict(reports))
    second = build_report_paragraphs(dict(reports))
    assert first == second


@pytest.mark.unit
def test_cit_t4_a_rerun_on_the_same_state_does_not_duplicate_annotations():
    """CIT-T4 / A3: annotations are derived from the stored raw text, never
    written into it, so re-resolving the same recorded turn — a resume, a
    re-export — yields it once, notices included, and the argument text is the
    model's own words."""
    from tradingagents.agents.citations import render_annotated_turn, resolve_turn

    paragraphs = DEFAULT_MAP  # pairs with _state()'s default reports
    first = resolve_turn("bear", 1, BEAR_TURN, paragraphs)
    again = resolve_turn("bear", 1, first["raw"], paragraphs)

    rendered = render_annotated_turn(first)
    assert rendered == render_annotated_turn(again)
    assert rendered.count(UNCITED) == 1
    assert rendered.count(INVALID) == 1
    assert [a["text"] for a in again["arguments"]] == [
        BEAR_ARG_1_TEXT, BEAR_ARG_2_TEXT, BEAR_ARG_3_TEXT,
    ]
    # The record keeps the model's text; the notices are not in it.
    assert first["raw"] == BEAR_TURN
    assert INVALID not in first["raw"] and UNCITED not in first["raw"]


# --- CIT-T8 dependency boundary -------------------------------------------


@pytest.mark.unit
def test_cit_t8_the_citation_leaf_is_imported_by_the_nodes_never_by_the_reports():
    """CIT-T8: the intended dependency boundary, not an import ban.

    ``citations`` is a leaf the researchers and the manager may import; it must
    import nothing from ``tradingagents.agents``, and the analyst/dataflow layers
    that must not depend on the debate contract must not reach it. The frontend
    entry points (the agents package re-export, the graph setup and the CLI
    display) may import it: an annotation shown only by the node would not
    survive resume or re-export.

    The manager is not required to import the leaf: it carries the recorded
    fields through rather than re-deriving them.
    """
    import ast
    import os

    import tradingagents.agents as agents_package
    from tradingagents.agents import citations  # noqa: F401  (the leaf under test)
    from tradingagents.agents.managers import research_manager
    from tradingagents.agents.researchers import bear_researcher, bull_researcher
    def imported_modules(path):
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        found = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module)
            elif isinstance(node, ast.Import):
                found.update(alias.name for alias in node.names)
        return found

    # The leaf imports nothing that would make reports depend on the debate.
    leaf_imports = imported_modules(citations.__file__)
    assert citations.__name__ == "tradingagents.agents.citations"
    assert not [m for m in leaf_imports
                if m == "tradingagents" or m.startswith(("tradingagents.agents",
                                                         "tradingagents.graph",
                                                         "tradingagents.dataflows"))], (
        sorted(leaf_imports))

    # The debate nodes derive annotations, so they import the leaf and no longer
    # parse IDs inline: every verdict comes from one implementation.
    for module in (bull_researcher, bear_researcher):
        assert module.__name__ in ("tradingagents.agents.researchers.bull_researcher",
                                   "tradingagents.agents.researchers.bear_researcher")
        assert "tradingagents.agents.citations" in imported_modules(module.__file__), (
            module.__name__)

    # The manager needs no citation logic: it only carries the recorded fields.
    manager_imports = imported_modules(research_manager.__file__)
    assert research_manager.__name__ == "tradingagents.agents.managers.research_manager"
    assert "tradingagents.agents.citations" not in manager_imports, (
        "the manager carries recorded fields; it must not re-derive them")

    # Layers that must not depend on the debate contract stay clear of it.
    root = os.path.dirname(agents_package.__file__)
    for path in (f"{root}/state.py", f"{root}/analysts/__init__.py", f"{root}/context.py"):
        assert "tradingagents.agents.citations" not in imported_modules(path), path


# --- CIT-T3 · fit criterion: no misplaced or ambiguous citation -----------


@pytest.mark.unit
def test_cit_t3_a_valid_id_is_never_also_reported_invalid():
    """Fit criterion 'wrongly flagged citation': a written, resolvable ID carries
    exactly one verdict and no notice."""
    from tradingagents.agents.citations import resolve_turn

    entry = resolve_turn("bull", 1, "Demand is intact [FUN-01] and margins held [FUN-02].",
                         report_map())
    claims = [c for a in entry["arguments"] for c in a["citations"]]
    assert [c["id"] for c in claims] == ["FUN-01", "FUN-02"]
    assert all(c["valid"] for c in claims)
    assert [a["note"] for a in entry["arguments"]] == [""]


@pytest.mark.unit
def test_cit_t3_an_id_from_another_report_is_never_rewritten():
    """Fit criterion 'misplaced citation': an ID that names another run paragraph
    is judged against the map as written — never interpreted as FUN-02."""
    from tradingagents.agents.citations import extract_citations

    positions = extract_citations("Margin fell [MKT-02] on the day.")
    assert [p["id"] for p in positions] == ["MKT-02"]
    assert positions[0]["position"] == len("Margin fell ")


# --- CIT-T9: graph layout and public interfaces unchanged -----------------


@pytest.mark.unit
def test_cit_t9_the_graph_layout_is_unchanged():
    """CIT-T9 / AGENTS.md: editing the bull/bear/manager nodes adds no node,
    edge or route. The workflow's own compiled nodes and static edges are
    compared with the layout FEAT-05 must leave untouched."""
    from tradingagents.graph.setup import GraphSetup

    plain_llm = RecordingLLM()
    workflow = GraphSetup(
        plain_llm, plain_llm, ConditionalLogic(max_debate_rounds=1), max_tool_rounds=1,
    ).setup_graph()
    view = workflow.compile().get_graph()
    nodes = set(view.nodes)
    edges = {(e.source, e.target) for e in view.edges}
    analysts = {"Market Analyst", "Sentiment Analyst", "News Analyst",
                "Fundamentals Analyst", "Options Analyst"}

    # The debate stage: analysts feed the bull only, then bull → bear → manager.
    assert nodes == analysts | {
        "__start__", "__end__", "Bull Researcher", "Bear Researcher", "Research Manager",
        "Trader", "Aggressive Analyst", "Conservative Analyst", "Neutral Analyst",
        "Portfolio Manager",
    }
    for analyst in analysts:
        assert (analyst, "Bull Researcher") in edges, analyst
        assert not [(s, t) for s, t in edges
                    if s == analyst and s != t
                    and t in ("Bear Researcher", "Research Manager")], analyst
    assert ("Research Manager", "Trader") in edges
    assert ("Trader", "Aggressive Analyst") in edges
    assert ("Portfolio Manager", "__end__") in edges
    # Only the two researchers reach the manager (at the cap), and the bear
    # reaches nothing past it. Self-loops are the routers' own target lists.
    assert {s for s, t in edges if t == "Research Manager"} == {
        "Bull Researcher", "Bear Researcher"}
    assert not [(s, t) for s, t in edges if s == "Bear Researcher" and s != t
                and t not in ("Research Manager", "Bull Researcher")]

    assert set(DEBATE_PATH_MAP) == {"Bull Researcher", "Bear Researcher", "Research Manager"}
    assert set(RISK_ANALYSIS_PATH_MAP) == {
        "Aggressive Analyst", "Conservative Analyst", "Neutral Analyst", "Portfolio Manager",
    }
    assert callable(Propagator.create_initial_state)


@pytest.mark.unit
def test_cit_t9_the_researcher_factories_keep_their_public_signatures():
    """CIT-T9: public imports and call shapes are preserved."""
    import inspect

    from tradingagents.agents import (
        create_bear_researcher as exported_bear,
        create_bull_researcher as exported_bull,
        create_research_manager as exported_manager,
    )
    from tradingagents.agents.managers.research_manager import create_research_manager
    from tradingagents.agents.researchers.bear_researcher import create_bear_researcher
    from tradingagents.agents.researchers.bull_researcher import create_bull_researcher

    assert exported_bear is create_bear_researcher
    assert exported_bull is create_bull_researcher
    assert exported_manager is create_research_manager
    assert list(inspect.signature(create_bull_researcher).parameters) == ["llm"]
    assert list(inspect.signature(create_bear_researcher).parameters) == ["llm", "judge"]
    assert inspect.signature(create_bear_researcher).parameters["judge"].default is None
    assert list(inspect.signature(create_research_manager).parameters) == ["llm"]
    assert set(ANALYST_NODE_SPECS) == {"market", "social", "news", "fundamentals", "options"}
