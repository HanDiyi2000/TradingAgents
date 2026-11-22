"""FEAT-05 / FR-CIT-01: citation evidence in exports, Options runs and resume.

Test-only patch, second file. Companion to ``test_debate_citations.py``: that
file fixes numbering, argument segmentation, extraction and state ownership;
this one fixes end-to-end behaviour — the report writers, the Options (FEAT-01)
and FEAT-02/FEAT-03 compatibility, the run log, and a real checkpointed run
interrupted and resumed.

Requirement: FR-CIT-01, cases CIT-T2 (export half), CIT-T5, CIT-T6, CIT-T7a/b,
with CIT-T1's export assertions included where they need the writer.

Nothing here is a pass until it runs against an implementation under review.
"""

from __future__ import annotations

import copy
import json
import re
from html import unescape

import pytest

from offline.test_debate_citations import (
    BEAR_ANNOTATED,
    BEAR_ARG_1_TEXT,
    BEAR_ARG_2_TEXT,
    BEAR_ARG_3_TEXT,
    BEAR_TURN,
    INVALID,
    UNCITED,
    RecordingLLM,
    _state,
    expected_map,
    report_texts,
)
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.reporting import write_report_tree

# --- what every paragraph must say, in both formats ------------------------

# The three bear arguments as rendered in Markdown: each notice trails its claim.
EXPECTED_BEAR = {
    "argument_1": BEAR_ARG_1_TEXT,                                  # valid, no notice
    "argument_2": f"{BEAR_ARG_2_TEXT} \u2014 *{INVALID}: FUN-99.*",  # invalid
    "argument_3": f"{BEAR_ARG_3_TEXT} \u2014 *{UNCITED}.*",          # uncited
}
# The same three arguments in HTML, where inline Markdown becomes elements: the
# rendered text carries the notice without its emphasis markers, and the claim
# still comes first.
EXPECTED_BEAR_HTML = {
    "argument_1": BEAR_ARG_1_TEXT,
    "argument_2": f"{BEAR_ARG_2_TEXT} \u2014 {INVALID}: FUN-99.",
    "argument_3": f"{BEAR_ARG_3_TEXT} \u2014 {UNCITED}.",
}
# The analyst paragraph the researchers and the report must agree on.
EXPECTED_SOURCE = {"FUN-01": "Revenue grew 10% on strong demand.",
                   "FUN-02": "Gross margin held at 62%."}


# --- export helpers --------------------------------------------------------


def _annotated(state_text, paragraphs, speaker="bear", turn=1):
    from tradingagents.agents.citations import render_annotated_turn, resolve_turn

    entry = resolve_turn(speaker, turn, state_text, paragraphs)
    return render_annotated_turn(entry), entry


def _finished_state(debate):
    """A finished run's state: the supplied debate and the rest of a run."""
    state = _state(debate=debate)
    state.update({
        "trader_investment_plan": "Trader plan.",
        "investment_plan": "**Recommendation**: Overweight",
        "final_trade_decision": "**Rating**: Overweight",
    })
    return state


def _scripted_run(bear_turn=BEAR_TURN):
    """A run whose real bear node recorded ``bear_turn`` (map built from absent).

    ``turn_citations`` is the list the bear node appended; ``history`` and
    ``bear_history`` are what it wrote.
    """
    from tradingagents.agents.researchers.bear_researcher import create_bear_researcher

    bull_turn = "Bull Analyst: Demand is intact."
    before = _state(debate={
        "history": bull_turn, "bull_history": "\n" + bull_turn,
        "current_response": bull_turn, "count": 1,
    })
    update = create_bear_researcher(RecordingLLM(bear_turn))(before)
    return _finished_state(update["investment_debate_state"])


def _export(state, tmp_path):
    """Write the report tree; return (markdown, html, individual responses)."""
    write_report_tree(state, "NVDA", tmp_path, settings={}, html=True)
    markdown = (tmp_path / "complete_report.md").read_text(encoding="utf-8")
    page = (tmp_path / "complete_report.html").read_text(encoding="utf-8")
    research = {
        name: (tmp_path / "2_research" / f"{name}.md").read_text(encoding="utf-8")
        for name in ("bull", "bear", "manager")
        if (tmp_path / "2_research" / f"{name}.md").exists()
    }
    return markdown, page, research


def markdown_blocks(text):
    """The reader-facing blocks of ``text``, blank-line separated.

    Fenced code and table rows are part of the block they belong to, so a
    paragraph that carries a notice stays one block even when it contains
    either, and a heading line never splits the paragraph below it.
    """
    blocks, current, fenced = [], [], False
    for line in (text or "").splitlines():
        if line.strip().startswith("```"):
            fenced = not fenced
            current.append(line)
            continue
        if fenced:
            current.append(line)
            continue
        if not line.strip():
            if current:
                blocks.append("\n".join(current).strip())
                current = []
            continue
        current.append(line)
    if current:
        blocks.append("\n".join(current).strip())
    return [unescape(block) for block in blocks if block]


def html_blocks(fragment):
    """The text of each block-level element in ``fragment``, tags stripped."""
    blocks = re.findall(r"<(p|li|td|th|h[1-6])[^>]*>(.*?)</\1>", fragment, flags=re.S)
    return [(tag, unescape(re.sub(r"<[^>]+>", "", body)).strip()) for tag, body in blocks]


def markdown_section(markdown, heading, following):
    return markdown.partition(heading)[2].partition(following)[0]


def html_section(page, section_id, following_id):
    return page.partition(f'id="{section_id}"')[2].partition(f'id="{following_id}"')[0]


def assert_notice_beside_its_claim(blocks):
    """The two notices each occur once, inside the block that carries that claim."""
    invalid = [b for b in blocks if b.count(INVALID) > 0]
    uncited = [b for b in blocks if b.count(UNCITED) > 0]
    assert len(invalid) == 1, f"{INVALID} must appear in exactly one block: {invalid}"
    assert len(uncited) == 1, f"{UNCITED} must appear in exactly one block: {uncited}"
    assert "FUN-99" in invalid[0], "the invalid notice is beside the invalid citation"
    assert "FUN-99" not in uncited[0], "the uncited notice is not on the invalid argument"
    assert "FUN-01" not in uncited[0] and "FUN-01" not in invalid[0]


def assert_arguments_rendered(blocks, expected=EXPECTED_BEAR):
    """Each approved argument sits verbatim in exactly one block.

    Called on a fragment holding only the recorded turns: the speaker's own
    label (``Bear Analyst:``) prefixes the first block of its turn.
    """
    joined = [block.removeprefix("Bear Analyst: ").removeprefix("Bull Analyst: ")
              for block in blocks]
    for argument, text in expected.items():
        assert joined.count(text) == 1, f"{argument}: {text!r} not in exactly one block"


# --- CIT-T2 export half: the three associations survive both formats ------


@pytest.mark.unit
def test_cit_t2_markdown_keeps_each_notice_beside_its_own_argument(tmp_path):
    """CIT-T2: in section II of complete_report.md each notice shares a block
    with its own claim, the valid pair keeps both IDs in place and takes none."""
    state = _scripted_run()

    markdown, _page, research = _export(state, tmp_path)
    section = markdown_section(markdown, "## II. Research Team Decision", "## III.")
    blocks = markdown_blocks(section)

    assert_notice_beside_its_claim(blocks)
    assert_arguments_rendered(blocks)
    assert research["bear"].strip() == state["investment_debate_state"]["bear_history"].strip()
    assert BEAR_ANNOTATED in research["bear"]


@pytest.mark.unit
def test_cit_t2_html_keeps_each_notice_beside_its_own_argument(tmp_path):
    """CIT-T2: in complete_report.html each notice is inside the paragraph that
    carries its claim — not merely somewhere in the same section."""
    state = _scripted_run()

    _, page, _research = _export(state, tmp_path)
    section = html_section(page, "s2", "s3")
    blocks = [body for _tag, body in html_blocks(section)]

    assert_notice_beside_its_claim(blocks)
    assert_arguments_rendered(blocks, EXPECTED_BEAR_HTML)


@pytest.mark.unit
def test_cit_t2_the_individual_and_consolidated_reports_cannot_disagree(tmp_path):
    """CIT-T2: the bear's own file, the consolidated Markdown and the HTML page
    render one recorded turn, so their notices are the same, once each."""
    state = _scripted_run()

    markdown, page, research = _export(state, tmp_path)
    section = markdown_section(markdown, "## II. Research Team Decision", "## III.")
    html = html_section(page, "s2", "s3")

    assert research["bear"].strip() == state["investment_debate_state"]["bear_history"].strip()
    for rendered in (research["bear"], section, html):
        assert rendered.count(INVALID) == 1, rendered[:200]
        assert rendered.count(UNCITED) == 1, rendered[:200]
    assert BEAR_ANNOTATED in research["bear"] and BEAR_ANNOTATED in section


# --- CIT-T1 export half ---------------------------------------------------


@pytest.mark.unit
def test_cit_t1_source_labels_survive_into_the_consolidated_report(tmp_path):
    """CIT-T1: the analyst section shows each ID beside its own original
    paragraph, in Markdown and in HTML — the same association the researchers
    were handed."""
    state = _scripted_run()

    markdown, page, _research = _export(state, tmp_path)

    analysts_md = markdown_section(markdown, "## I. Analyst Team Reports", "## II.")
    analysts_html = html_section(page, "s1", "s2")
    for label, text in EXPECTED_SOURCE.items():
        assert f"[{label}] {text}" in analysts_md, label
        assert any(f"[{label}]" in body and text in body
                   for _tag, body in html_blocks(analysts_html)), label

    bear_md = markdown_section(markdown, "### Bear Researcher", "### Research Manager")
    blocks_md = markdown_blocks(bear_md)
    assert_notice_beside_its_claim(blocks_md)
    assert_arguments_rendered(blocks_md, EXPECTED_BEAR)

    # The same subsection of the page: the bear's own <h3> to the manager's.
    start = page.index(">Bear Researcher</h3>") + len(">Bear Researcher</h3>")
    end = page.index(">Research Manager</h3>")
    blocks_html = [body for _tag, body in html_blocks(page[start:end])]
    assert_notice_beside_its_claim(blocks_html)
    assert_arguments_rendered(blocks_html, EXPECTED_BEAR_HTML)


# --- CIT-T5: Options report (FEAT-01) ------------------------------------


@pytest.mark.unit
def test_cit_t5_options_report_is_numbered_and_its_citations_validate():
    """CIT-T5 / FR-OPT-02+FR-CIT-01: an options-only run numbers from OPT-01 and
    an options-cited argument validates against this run's map."""
    from tradingagents.agents.citations import build_report_paragraphs, resolve_turn

    texts = report_texts(exclude=("market", "sentiment", "news", "fundamentals"),
                         options="## Chain\n\nATM IV is 25%.\n\nSpreads widened to 0.2.")
    options_only = {key: texts[key] for key in
                    ("market_report", "sentiment_report", "news_report",
                     "fundamentals_report", "options_report")}
    paragraphs = build_report_paragraphs(options_only)
    assert [p["id"] for p in paragraphs] == ["OPT-01", "OPT-02"]
    assert [p["text"] for p in paragraphs] == ["ATM IV is 25%.", "Spreads widened to 0.2."]

    entry = resolve_turn("bull", 1, "Call skew is heavy [OPT-02].", paragraphs)
    assert [c["id"] for c in entry["arguments"][0]["citations"]] == ["OPT-02"]
    assert entry["arguments"][0]["citations"][0]["valid"] is True
    assert entry["arguments"][0]["note"] == ""


@pytest.mark.unit
def test_cit_t5_the_options_analyst_path_is_unchanged_offline(monkeypatch):
    """CIT-T5 / FR-OPT-05: an ineligible chain still yields the unchanged
    unavailable notice (FEAT-05 must not touch the options analyst)."""
    from tradingagents.agents.analysts import options_analyst

    notice = (
        "Options data unavailable for NVDA as of 2026-01-09. No eligible option-chain "
        "observations were available for this instrument on that date. This report "
        "contains no options evidence and no inferred options signal."
    )
    monkeypatch.setattr(options_analyst, "load_eligible_option_chain",
                        lambda *a, **k: type("E", (), {"usable": False})())

    result = options_analyst.create_options_analyst(RecordingLLM())({
        "company_of_interest": "NVDA", "trade_date": "2026-01-09", "messages": [],
    })
    assert result["options_report"] == notice


@pytest.mark.unit
def test_cit_t5_options_only_run_numbers_from_opt_01_end_to_end(tmp_path):
    """CIT-T5: a finished options-only run exports OPT-01 and no other source."""
    texts = report_texts(exclude=("market", "sentiment", "news", "fundamentals"),
                         options="## Chain\n\nATM IV is 25%.")
    state = _state(texts, expected_map(texts))

    write_report_tree(state, "NVDA", tmp_path, settings={}, html=True)
    markdown = (tmp_path / "complete_report.md").read_text(encoding="utf-8")

    assert "[OPT-01] ATM IV is 25%." in markdown
    assert "[FUN-01]" not in markdown and "[MKT-01]" not in markdown
    assert "[SEN-01]" not in markdown and "[NWS-01]" not in markdown


# --- CIT-T6: compatibility with FEAT-02, FEAT-03 and old state/logs -------


@pytest.mark.unit
def test_cit_t6_the_company_background_carries_no_paragraph_ids(tmp_path, monkeypatch):
    """CIT-T6 / FR-RPT-01+FR-CIT-01: the background keeps its FEAT-03 position
    and content and receives no citation labels."""
    from tradingagents.dataflows import date_window

    today = "2026-11-23"
    monkeypatch.setattr(date_window, "get_current_date", lambda: today)
    state = _scripted_run()
    state["trade_date"] = today
    # The shared view FEAT-03 builds from ``company_identity`` (name + fields).
    state["company_identity"] = {
        "company_name": "NVIDIA", "industry": "Semiconductors",
        "business_description": "Designs accelerated computing platforms. Sells to cloud buyers.",
    }

    markdown, page, _research = _export(state, tmp_path)

    background = markdown_section(markdown, "## Company Background", "## I.")
    assert "NVIDIA" in background and "Semiconductors" in background
    for marker in ("[FUN-", "[MKT-", INVALID, UNCITED):
        assert marker not in background, marker
    assert markdown.index("## Company Background") < markdown.index("## I. Analyst Team Reports")

    background_html = html_section(page, "company-background", "s1")
    assert "NVIDIA" in background_html and "Semiconductors" in background_html
    for marker in ("[FUN-", "[MKT-", INVALID, UNCITED):
        assert marker not in background_html, marker
    assert page.index('id="company-background"') < page.index('id="s1"')


@pytest.mark.unit
def test_cit_t6_old_state_without_citation_fields_still_exports_and_displays(tmp_path, capsys):
    """CIT-T6: a baseline state (no map, no records) keeps exporting unchanged
    and its unchanged recorded turn displays without error."""
    from cli.display import display_complete_report

    state = _state()
    state["investment_debate_state"]["history"] = "Bear Analyst: plain turn."
    state["investment_debate_state"]["bear_history"] = "\nBear Analyst: plain turn."

    markdown, page, research = _export(state, tmp_path)
    assert "plain turn" in markdown and "plain turn" in page
    assert "plain turn" in research["bear"]
    assert INVALID not in markdown and UNCITED not in markdown

    display_complete_report(state)
    out = capsys.readouterr().out
    assert "plain turn" in out


@pytest.mark.unit
def test_cit_t6_the_run_log_carries_the_map_and_citations_additively(tmp_path):
    """CIT-T6: the JSON run log gains the map and the records beside the old
    keys, which keep their values."""
    state = _scripted_run()
    debate = state["investment_debate_state"]
    before = {key: copy.deepcopy(debate[key]) for key in
              ("bull_history", "bear_history", "history", "current_response")}

    graph = _log_only_graph(tmp_path)
    graph._log_state("2026-01-09", state)

    log = _run_log(tmp_path)["investment_debate_state"]
    for key, value in before.items():
        assert log[key] == value, key
    assert log["report_paragraphs"] == debate["report_paragraphs"]
    assert [e["speaker"] for e in log["turn_citations"]] == ["bear"]
    assert [c["id"] for c in log["turn_citations"][0]["arguments"][1]["citations"]] == ["FUN-99"]
    assert log["turn_citations"][0]["arguments"][1]["note"] == INVALID
    assert log["turn_citations"][0]["arguments"][2]["note"] == UNCITED


@pytest.mark.unit
def test_cit_t6_an_old_log_without_the_fields_still_loads(tmp_path):
    """CIT-T6: a saved log from before FEAT-05 keeps every key it had.

    The comparison is against the keys the run log defines, not the raw state:
    ``count`` was never logged, so it must not be required of the log.
    """
    state = _state(debate={"history": "Bear Analyst: plain turn.",
                           "bear_history": "\nBear Analyst: plain turn.", "count": 2})
    logged = ("bull_history", "bear_history", "history", "current_response")

    graph = _log_only_graph(tmp_path)
    graph._log_state("2026-01-09", state)

    log = _run_log(tmp_path)["investment_debate_state"]
    for key in logged:
        assert log[key] == state["investment_debate_state"][key], key
    # The state carried no map and no records, so the log adds none of its own.
    assert log["report_paragraphs"] == []
    assert log["turn_citations"] == []
    assert INVALID not in json.dumps(log) and UNCITED not in json.dumps(log)


def _log_only_graph(tmp_path, **config):
    """A graph used for its run log only: no model is created until a run."""
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg.update(results_dir=str(tmp_path / "logs"), data_cache_dir=str(tmp_path / "cache"),
               memory_log_path=str(tmp_path / "log.md"), **config)
    return TradingAgentsGraph(config=cfg)


def _run_log(root):
    import pathlib

    path = sorted(pathlib.Path(root).rglob("full_states_log*.json"))[-1]
    return json.loads(path.read_text(encoding="utf-8"))


# --- CIT-T7: a real checkpointed run, interrupted and resumed -------------


def _offline_vendors(monkeypatch, tmp_path):
    """The existing offline fixture's setup, for the checkpointed runs.

    Called directly rather than requested so the dependency is explicit: the
    same vendor stubs the rest of the offline suite runs on.
    """
    from offline.test_graph_end_to_end import offline as _fixture

    return _fixture.__wrapped__(monkeypatch, tmp_path)


def _resume_graph(tmp_path, monkeypatch, model, **config):
    """A checkpointed graph on scripted models (the existing E2E pattern)."""
    from offline.test_graph_end_to_end import _Client
    from tradingagents.graph import trading_graph

    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg.update(
        results_dir=str(tmp_path / "results"),
        data_cache_dir=str(tmp_path / "cache"),
        memory_log_path=str(tmp_path / "log.md"),
        checkpoint_enabled=True,
        **config,
    )
    monkeypatch.setattr(trading_graph, "create_tier_client",
                        lambda config, tier, **k: _Client(model))
    return trading_graph.TradingAgentsGraph(config=cfg)


def _checkpoint_debate(graph, ticker, trade_date):
    """The newest debate state the interrupted run saved. Fails if there is none."""
    import sqlite3

    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    from tradingagents.graph.checkpointer import _db_path, thread_id

    thread = thread_id(ticker, str(trade_date), graph._run_signature("stock", None))
    with sqlite3.connect(_db_path(graph.config["data_cache_dir"], ticker)) as conn:
        row = conn.execute(
            "select type, checkpoint from checkpoints where thread_id = ? "
            "order by checkpoint_id desc limit 1", (thread,),
        ).fetchone()
    assert row is not None, "the interrupted run must have saved a checkpoint"
    state = JsonPlusSerializer().loads_typed((row[0], bytes(row[1])))
    return dict(state["channel_values"].get("investment_debate_state") or {})


def _record_nodes(graph):
    """Record the graph node that runs each step, in order.

    Wraps every node's function so the test can tell which work a resumed run
    re-executed. Deterministic output alone cannot prove resumption: a restart
    reproduces the same text, so only the executed nodes show what was repeated.
    A node that raises is recorded in ``seen`` as entered, and the failure is
    re-raised, so the caller can name the node that actually failed.
    """
    seen: list[str] = []
    for name, node in graph.graph.nodes.items():
        action = node.bound
        original = getattr(action, "func", None)
        if not callable(original):
            continue

        def wrapper(state, _original=original, _name=name, **kwargs):
            seen.append(_name)
            return _original(state, **kwargs)

        action.func = wrapper
    return seen


def _failed_node(graph, seen):
    """The node an interrupted run failed inside: the last one entered.

    The model fails inside the node that is running, so that node is entered
    and recorded, and the checkpoint holds the state from before it.
    """
    assert seen, "the interrupted run must have entered a node"
    return seen[-1]


def _call_count(model):
    """Every model call the scripted model has made so far, failures included."""
    return len(model.calls)


# The scripted model answers every turn with one line that the bear node
# annotates; ``_log_state`` keeps the recorded history verbatim.
_PLAIN_TURN = "Report.\n\n**Rating**: Overweight\n\nFINAL TRANSACTION PROPOSAL: **BUY**"


@pytest.mark.unit
def test_cit_t7b_a_run_interrupted_after_the_bull_reuses_the_stored_map(
    tmp_path, monkeypatch,
):
    """CIT-T7b: interrupted after the bull's turn, the resumed run keeps the map
    the checkpoint holds, does not renumber, and adds exactly one notice per
    argument of each bear turn it writes — never a second for the same turn.

    The scripted model fails inside the node that is running. At fail_at=9 that
    is the bear node: the bull's turn is already written to the checkpoint, so
    the bull must not run again and the bear must be retried.
    """
    from offline.test_graph_end_to_end import TRADE_DATE, ScriptedModel

    _offline_vendors(monkeypatch, tmp_path)
    # Measured on the offline scripted model, per call index (nodes entered in
    # brackets):
    #   fail_at=8  → count 0, fails inside [Bull Researcher]; no turn recorded
    #   fail_at=9  → count 1, fails inside [Bear Researcher]; bull turn recorded
    #   fail_at=10 → count 2, fails inside [Research Manager]; both turns recorded
    model = ScriptedModel(fail_at=9)
    graph = _resume_graph(tmp_path, monkeypatch, model)
    nodes = _record_nodes(graph)
    with pytest.raises(RuntimeError):
        graph.propagate("NVDA", TRADE_DATE)

    entered = list(nodes)
    failed_in = _failed_node(graph, entered)
    assert failed_in == "Bear Researcher", (
        f"at fail_at=9 the run must fail inside the bear node; it failed in {failed_in}")

    stored = _checkpoint_debate(graph, "NVDA", TRADE_DATE)
    assert stored.get("count") == 1, "the interruption must land after the bull turn"
    bull_history = stored["bull_history"]
    assert bull_history.strip().startswith("Bull Analyst:")
    assert stored["report_paragraphs"], "the bull turn must have built the map"
    # The bull's scripted turn cites nothing, so it is uncited — and the
    # checkpoint must already show that, since the checkpoint came after it.
    assert UNCITED in bull_history, "the checkpoint holds the recorded, annotated turn"
    assert INVALID not in bull_history, "the bull never wrote an invalid ID"

    failed_call = _call_count(model)
    nodes_before = len(nodes)

    _, signal = graph.propagate("NVDA", TRADE_DATE)

    resumed = _run_log(tmp_path)["investment_debate_state"]
    assert signal == "Overweight"

    # Resumed, not restarted, shown by executed nodes rather than by output: the
    # work that completed before the interruption runs again zero times, and the
    # node that failed is the only one retried.
    replayed = list(nodes[nodes_before:])
    assert replayed, "the resumed run must execute the remaining nodes"
    completed = set(entered) - {failed_in}
    for name in completed:
        assert name not in replayed, (
            f"{name} completed before the interruption; it must not re-run")
    assert "Bull Researcher" not in replayed, (
        "the bull's turn is in the checkpoint; it must not be re-executed")
    assert replayed[0] == failed_in, (
        f"the failed node {failed_in} must be the first thing retried")
    assert _call_count(model) > failed_call, "the resumed run must make the pending calls"

    # Resumed, not restarted: the bull turn recorded before the interruption is
    # still there, once, as the opening of the history.
    assert resumed["history"] == stored["history"] + resumed["history"][len(stored["history"]):]
    assert resumed["bull_history"] == bull_history
    assert resumed["history"].count("Bull Analyst:") == 1
    assert resumed["report_paragraphs"] == stored["report_paragraphs"]

    # Per-argument notices for both speakers, exactly once per argument: a
    # re-annotated turn would carry a second notice on its own claim.
    for history in (resumed["bull_history"], resumed["bear_history"]):
        assert_notice_once_per_argument(history)


@pytest.mark.unit
def test_turn_texts_helper_contract():
    """The helper the resume assertions rely on: turns are ``Speaker: text``."""
    text = "\nBull Analyst: a\n\nb\nBear Analyst: c [FUN-01]"
    assert turn_texts(text) == ["Bull Analyst: a\n\nb", "Bear Analyst: c [FUN-01]"]
    assert turn_texts("") == [] and turn_texts(None) == []
    # A body mentioning another speaker mid-sentence is one turn, not two: only
    # a line that starts with a speaker label begins a turn.
    assert turn_texts("Bear Analyst: asked the Bull Analyst: why?") == [
        "Bear Analyst: asked the Bull Analyst: why?"]
    assert_notice_once_per_argument(
        "Bear Analyst: one [FUN-01].\n\nTwo [MKT-99] \u2014 *Invalid citation: MKT-99.*")


def turn_texts(history):
    """Each ``<Speaker> Analyst:`` turn in ``history``, as recorded."""
    return [f"{speaker} Analyst: {body.strip()}"
            for speaker, body in re.findall(
                r"(?m)^(Bull|Bear) Analyst: (.*?)(?=^Bull Analyst: |^Bear Analyst: |\Z)",
                history or "", flags=re.S)
            if body.strip()]


@pytest.mark.unit
def test_notice_helpers_have_the_contract_the_resume_assertions_use():
    """The helpers the resume cases rely on, including the ways they must fail.

    Every negative here is a real defect the helper must catch, and is asserted
    through ``pytest.raises(AssertionError)``: a notice repeated inside one
    argument; an argument with no citation and no notice whose turn cites
    something elsewhere (the case a turn-level check would miss); an uncited
    argument that wrongly takes the invalid notice; and the first bull argument
    being skipped altogether.
    """
    good = ("Bull Analyst: uncited opening \u2014 *No citation provided.*\n\n"
            "Bear Analyst: valid [FUN-01].\n\n"
            "invalid [MKT-99] \u2014 *Invalid citation: MKT-99.*")
    assert_notice_once_per_argument(good)

    doubled = "Bear Analyst: one \u2014 *No citation provided.* *No citation provided.*"
    with pytest.raises(AssertionError):
        assert_notice_once_per_argument(doubled)

    # A citation earlier in the turn must not excuse a later uncited argument.
    suppressed = ("Bear Analyst: valid [FUN-01].\n\n"
                  "Uncited claim with no notice at all.")
    with pytest.raises(AssertionError):
        assert_notice_once_per_argument(suppressed)

    # The first bull argument is validated too, not skipped as a label: here it
    # cites nothing and carries no notice, so only a per-argument check catches
    # it (the turn as a whole does carry the invalid notice further down).
    bull_missing = ("Bull Analyst: Demand is intact.\n\n"
                    "Volume rose [FUN-01] \u2014 *Invalid citation: FUN-99.*")
    with pytest.raises(AssertionError):
        assert_notice_once_per_argument(bull_missing)

    # An uncited argument may not take the invalid notice instead.
    wrong_notice = "Bear Analyst: no ID here \u2014 *Invalid citation: FUN-99.*"
    with pytest.raises(AssertionError):
        assert_notice_once_per_argument(wrong_notice)

    bull_ok = ("Bull Analyst: Demand is intact \u2014 *No citation provided.*\n\n"
               "Volume rose [FUN-01] \u2014 *Invalid citation: FUN-99.*")
    assert_notice_once_per_argument(bull_ok)


def _arguments_of_turn(turn):
    """The arguments of one recorded turn, with the speaker label removed.

    The label belongs to the turn, not to its first argument, so removing it
    lets that first argument be validated like every other one.
    """
    body = re.sub(r"^(?:Bull|Bear) Analyst: ", "", turn)
    return [a for a in re.split(r"\n[ \t]*\n", body) if a.strip()]


def citation_ids(argument):
    """The IDs an argument cites, as written.

    An ID that appears inside a notice is the notice's own subject, not a
    citation the argument makes, so it is not counted.
    """
    claims = argument
    for notice in (INVALID, UNCITED):
        claims = re.sub(re.escape(notice) + r":?[^.*]*", "", claims)
    return re.findall(r"\[([A-Z]{3}-[0-9]{2})\]", claims)


def assert_notice_once_per_argument(history):
    """Validate every recorded argument on its own.

    Each argument is checked independently of the rest of its turn:
      - neither notice appears twice in it (a duplicated annotation);
      - an argument citing nothing carries ``No citation provided``;
      - an argument with a citation does not carry the uncited notice;
      - an argument that already carries a notice is not additionally credited
        with the citation(s) that notice names.
    Whether a cited ID resolves is decided by the map, so it is asserted where
    the map is known, not here.
    """
    for turn in turn_texts(history):
        for argument in _arguments_of_turn(turn):
            for notice in (INVALID, UNCITED):
                assert argument.count(notice) <= 1, (
                    f"{notice!r} appears twice in one argument: {argument!r}")
            ids = citation_ids(argument)
            if not ids:
                assert UNCITED in argument, (
                    f"argument cites nothing and carries no uncited notice: {argument!r}")
                assert INVALID not in argument, (
                    f"an uncited argument also carries an invalid notice: {argument!r}")
            else:
                assert UNCITED not in argument, (
                    f"argument cites {ids} and still carries an uncited notice: {argument!r}")
                # A fully valid argument takes no notice; one with an unknown ID
                # must take the invalid notice. Which is which is decided by the
                # map, so the caller asserts the known-map case separately.


@pytest.mark.unit
def test_cit_t7a_a_run_interrupted_before_the_first_researcher_numbers_once(
    tmp_path, monkeypatch,
):
    """CIT-T7a: interrupted with no map yet (the field is absent), the resumed
    run numbers on its first researcher turn, identically to a fresh run, and
    the analysts — already finished before the interruption — are not re-run."""
    from offline.test_graph_end_to_end import TRADE_DATE, ScriptedModel

    _offline_vendors(monkeypatch, tmp_path)
    fresh_model = ScriptedModel()
    fresh = _resume_graph(tmp_path / "fresh", monkeypatch, fresh_model)
    fresh_nodes = _record_nodes(fresh)
    fresh.propagate("NVDA", TRADE_DATE)
    expected = _run_log(tmp_path / "fresh")["investment_debate_state"]

    # fail_at=8: after the analysts, before any researcher (measured offline).
    model = ScriptedModel(fail_at=8)
    interrupted = _resume_graph(tmp_path, monkeypatch, model)
    nodes = _record_nodes(interrupted)
    with pytest.raises(RuntimeError):
        interrupted.propagate("NVDA", TRADE_DATE)
    ran_before, nodes_before = list(nodes), len(nodes)
    # The scripted model fails inside the bull node, so that node is entered and
    # recorded, but it completed nothing: the run failed before any turn.
    failed_in = _failed_node(interrupted, ran_before)
    assert failed_in == "Bull Researcher", ran_before
    pending = _checkpoint_debate(interrupted, "NVDA", TRADE_DATE)
    assert pending["count"] == 0
    assert "report_paragraphs" not in pending, (
        "the map must be built before the first researcher call, not by "
        "initialization: a checkpoint here must not carry one"
    )

    _, signal = interrupted.propagate("NVDA", TRADE_DATE)
    resumed = _run_log(tmp_path)["investment_debate_state"]
    replayed = list(nodes[nodes_before:])

    assert signal == "Overweight"
    # Resumed, not restarted: every node that completed before the interruption
    # runs again zero times. The bull node was entered and failed, so it is not
    # a completed node; it is retried and completes.
    for name in set(ran_before) - {failed_in}:
        assert name not in replayed, (
            f"{name} completed before the interruption; it must not re-run")
    assert replayed[0] == failed_in, "the failed bull node must be the first retried"
    # The resumed run executes exactly the bull turns a fresh run executes, and
    # the bear turns the interruption left pending. (The bull node entered at
    # the interruption completed nothing, so it is not subtracted.)
    assert replayed.count("Bull Researcher") == fresh_nodes.count("Bull Researcher"), (
        "the resumed run executes the bull turns a fresh run executes")
    assert (replayed.count("Bear Researcher")
            == fresh_nodes.count("Bear Researcher")
            - ran_before.count("Bear Researcher")), (
        "the resumed run executes only the bear turns the interruption left pending")

    assert resumed["report_paragraphs"] == expected["report_paragraphs"]
    assert resumed["report_paragraphs"], "the resumed run must have built the map"
    # Same numbering as the fresh run, and the same turns' notices.
    assert resumed["bull_history"].count("Bull Analyst:") == expected["bull_history"].count(
        "Bull Analyst:")
    assert resumed["bear_history"].count("Bear Analyst:") == expected["bear_history"].count(
        "Bear Analyst:")


@pytest.mark.unit
def test_cit_t7_the_run_signature_is_unchanged(tmp_path, monkeypatch):
    """CIT-T7: FEAT-05 adds no configuration, so existing checkpoints still match."""
    from offline.test_graph_end_to_end import ScriptedModel

    graph = _resume_graph(tmp_path, monkeypatch, ScriptedModel())
    signature = graph._run_signature("stock", None)

    assert "report_paragraphs" not in signature
    assert "citation" not in signature
    assert graph._run_signature("stock", None) == signature
