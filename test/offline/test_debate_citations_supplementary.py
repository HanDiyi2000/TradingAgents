"""FEAT-05 supplementary tests: uncovered defects found during implementation review.

A supplementary, test-only patch. The approved contract in
``test_debate_citations.py`` and ``test_debate_citations_exports.py`` is
unchanged and keeps its approved hashes; these cases cover six defects that the
approved tests did not exercise.

Nothing here is a pass until it runs against the corrected implementation.

Findings covered:

1. Neither researcher prompt instructs the model to cite the source paragraph
   IDs beside each report-based argument (the labels appear, but the model is
   never told to use them).
2. ``report_paragraphs`` and ``turn_citations`` are required TypedDict keys,
   despite the approved NotRequired contract.
3. Numbering generates three-digit labels (``FUN-100``) once a report exceeds 99
   paragraphs, but extraction accepts only two digits and reports
   ``[FUN-100]`` as uncited.
4. ``split_arguments`` treats a standalone heading as an argument.
5. Source fenced code containing blank lines is split and numbered, contrary to
   the approved fenced-code rule; the debate fence has the same defect.
6. The first bull record has ``turn=1`` while the first bear has ``turn=2``:
   the two speakers number their own turns differently.
"""

from __future__ import annotations

import re
from html import unescape

import pytest

from offline.test_debate_citations import DEFAULT_MAP, RecordingLLM, _state, report_map
from tradingagents.agents.citations import (
    build_report_paragraphs,
    extract_citations,
    render_annotated_turn,
    resolve_turn,
    split_arguments,
)

INVALID = "Invalid citation"
UNCITED = "No citation provided"


def _empty_reports(**overrides):
    """Every report empty except the ones named, so IDs are easy to reason about."""
    reports = dict.fromkeys(
        ("market_report", "sentiment_report", "news_report",
         "fundamentals_report", "options_report"), "")
    reports.update(overrides)
    return reports


def _research_prompts():
    """(bull prompt, bear prompt) from run states with the stored map supplied."""
    from tradingagents.agents.researchers.bear_researcher import create_bear_researcher
    from tradingagents.agents.researchers.bull_researcher import create_bull_researcher

    bull_llm = RecordingLLM()
    create_bull_researcher(bull_llm)(_state(paragraphs=DEFAULT_MAP, debate={"count": 0}))
    bear_llm = RecordingLLM()
    create_bear_researcher(bear_llm)(_state(
        paragraphs=DEFAULT_MAP,
        debate={"count": 1, "current_response": "Bull Analyst: Demand is intact."},
    ))
    return bull_llm.prompt_text, bear_llm.prompt_text


# --- Finding 1: the prompt must ask the model to cite ----------------------


@pytest.mark.unit
def test_supp_the_researchers_are_told_to_cite_the_paragraph_ids():
    """Finding 1: both researchers receive an explicit instruction to place a
    source paragraph ID in brackets beside each argument taken from a report, so
    the mapping is usable rather than merely displayed."""
    for name, prompt in zip(("bull", "bear"), _research_prompts(), strict=True):
        lowered = prompt.lower()
        assert "cite" in lowered or "citation" in lowered, (
            f"the {name} prompt never asks the model to cite")
        # The instruction names the label form the reports carry.
        assert re.search(r"\[(?:MKT|FUN|SEN|NWS|OPT)-\d{2,}\]", prompt), (
            f"the {name} prompt does not show the label form")
        # It says where the label belongs: beside the argument it supports.
        assert re.search(r"(beside|after|next to|alongside|following)", lowered), (
            f"the {name} prompt does not say where the citation belongs")
        # And what to do when a claim rests on no supplied report.
        assert re.search(r"(not take|no source|without a|do not cite|no citation|"
                         r"not from|no report|not based)", lowered), (
            f"the {name} prompt does not say what to do for an unsupported claim")


# --- Finding 2: the new fields must be NotRequired -------------------------


@pytest.mark.unit
def test_supp_the_citation_fields_are_optional_state_keys():
    """Finding 2: older states, logs and checkpoints lack the two fields, so the
    approved contract makes them optional; a TypedDict that requires them
    contradicts it."""
    from tradingagents.agents.state import InvestDebateState

    required = getattr(InvestDebateState, "__required_keys__", set())
    optional = getattr(InvestDebateState, "__optional_keys__", set())

    for key in ("report_paragraphs", "turn_citations"):
        assert key in InvestDebateState.__annotations__, key
        assert key not in required, f"{key} must not be a required key"
        assert key in optional, f"{key} must be declared NotRequired"

    # The fields the debate already relies on stay as they were.
    for key in ("bull_history", "bear_history", "history", "current_response", "count"):
        assert key in required, key


# --- Finding 3: three-digit numbering must round-trip ----------------------


@pytest.mark.unit
def test_supp_a_report_beyond_ninety_nine_paragraphs_round_trips():
    """Finding 3: the numbering continues past two digits, and a written label
    of that width resolves against the map instead of being called uncited."""
    report = "\n\n".join(f"Paragraph {n} of a long report." for n in range(1, 121))
    paragraphs = build_report_paragraphs(_empty_reports(fundamentals_report=report))

    ids = [p["id"] for p in paragraphs]
    assert ids[0] == "FUN-01" and ids[98] == "FUN-99", ids[:3] + ids[97:100]
    assert ids[99] == "FUN-100" and ids[-1] == "FUN-120", ids[98:]

    # A written label of the generated width is extracted and resolves.
    written = "Late data matters [FUN-100] to the case."
    positions = extract_citations(written)
    assert [p["id"] for p in positions] == ["FUN-100"], positions

    entry = resolve_turn("bear", 1, written, paragraphs)
    argument = entry["arguments"][0]
    assert [c["id"] for c in argument["citations"]] == ["FUN-100"]
    assert argument["citations"][0]["valid"] is True
    assert argument["note"] == "", "a valid three-digit label must not be flagged"
    assert INVALID not in render_annotated_turn(entry)
    assert UNCITED not in render_annotated_turn(entry)

    # An unknown three-digit label is still an invalid citation, not a missing one.
    missing = resolve_turn("bear", 1, "Unknown [FUN-121].", paragraphs)
    assert [c["id"] for c in missing["arguments"][0]["citations"]] == ["FUN-121"]
    assert missing["arguments"][0]["citations"][0]["valid"] is False
    assert missing["arguments"][0]["note"] == INVALID


@pytest.mark.unit
def test_supp_two_digit_labels_keep_their_exact_meaning():
    """Finding 3 regression: widening the label pattern must not reinterpret an
    existing two-digit ID, and a three-digit prefix must not match a two-digit
    one by truncation."""
    paragraphs = build_report_paragraphs(_empty_reports(
        fundamentals_report="One.\n\nTwo."))

    assert [c["id"] for c in extract_citations("See [FUN-01].")] == ["FUN-01"]
    entry = resolve_turn("bear", 1, "See [FUN-01].", paragraphs)
    assert entry["arguments"][0]["citations"][0]["valid"] is True

    beyond = resolve_turn("bear", 1, "See [FUN-100].", paragraphs)
    assert [c["id"] for c in beyond["arguments"][0]["citations"]] == ["FUN-100"], (
        "a three-digit label must not be read as FUN-10 followed by a stray digit")
    assert beyond["arguments"][0]["note"] == INVALID


# --- Finding 4: a standalone heading is not an argument --------------------


@pytest.mark.unit
def test_supp_a_standalone_heading_is_not_an_argument():
    """Finding 4: a heading is a section label, not a claim. It carries no
    citation and must not take an uncited notice, and it must not split the
    argument beneath it."""
    arguments = split_arguments("## Risks\n\nMargins fell [FUN-01].")
    assert [a.text for a in arguments] == ["Margins fell [FUN-01]."], arguments

    entry = resolve_turn("bear", 1, "## Risks\n\nMargins fell [FUN-01].", report_map())
    assert [a["text"] for a in entry["arguments"]] == ["Margins fell [FUN-01]."]
    assert [a["note"] for a in entry["arguments"]] == [""], (
        "the valid argument takes no notice and the heading adds none")
    rendered = render_annotated_turn(entry)
    assert rendered == "Margins fell [FUN-01]."
    assert UNCITED not in rendered


@pytest.mark.unit
def test_supp_a_heading_directly_above_its_paragraph_stays_out_of_it():
    """Finding 4: the same rule when no blank line separates the heading from
    its body, matching the source-report rule."""
    arguments = split_arguments("### Outlook\nDemand is opaque.")
    assert [a.text for a in arguments] == ["Demand is opaque."], arguments


# --- Finding 5: a fenced block is never split ------------------------------


@pytest.mark.unit
def test_supp_source_fenced_code_is_kept_intact_and_unnumbered(tmp_path):
    """Finding 5: a fenced block in a report is left whole and receives NO
    paragraph ID. It is not split (so its blank lines never make two
    paragraphs) and it is not numbered (so the model cannot cite code as
    evidence). Only Intro and Outro take IDs."""
    from offline.test_debate_citations_exports import _export, _finished_state, _state

    report = "Intro [FUN-01].\n\n```\na=1\n\nb=2\n```\n\nOutro."
    paragraphs = build_report_paragraphs(_empty_reports(fundamentals_report=report))

    assert [(p["id"], p["text"]) for p in paragraphs] == [
        ("FUN-01", "Intro [FUN-01]."),
        ("FUN-02", "Outro."),
    ], paragraphs
    assert not any("```" in p["text"] for p in paragraphs), (
        "no ID may be attached to a fenced block, whole or in part")

    # The researcher input keeps the complete, unnumbered code block.
    texts = dict(_empty_reports(fundamentals_report=report))
    state = _state(texts, paragraphs=paragraphs, debate={"count": 0})
    prompt = _research_prompt(state)
    assert "```\na=1\n\nb=2\n```" in prompt, "the full fenced block must reach the model"
    assert "[FUN-01] Intro [FUN-01]." in prompt and "[FUN-02] Outro." in prompt
    assert "[FUN-01] ```" not in prompt and "[FUN-02] ```" not in prompt
    assert prompt.count("```") == 2, "the code block stays a single pair of fences"

    # Both exports preserve it too: nothing is silently dropped.
    finished = _finished_state(dict(state["investment_debate_state"]))
    finished.update(texts)
    finished["market_report"] = ""  # only the fenced report is under test
    markdown, page, _research = _export(finished, tmp_path)
    for rendered, name in ((markdown, "Markdown"), (page, "HTML")):
        assert "a=1" in rendered and "b=2" in rendered, f"{name} dropped the code block"
        assert rendered.count("```") % 2 == 0 or name == "HTML"
    analysts_md = markdown.partition("## I. Analyst Team Reports")[2].partition("## II.")[0]
    assert "```\na=1\n\nb=2\n```" in analysts_md, "the Markdown report keeps the block whole"
    assert "[FUN-01] Intro [FUN-01]." in analysts_md
    assert "[FUN-02] Outro." in analysts_md
    assert "[FUN-01] ```" not in analysts_md and "[FUN-02] ```" not in analysts_md

    # The HTML analyst section holds exactly one <pre><code> element — the whole
    # fenced block — with no paragraph ID inside it.
    analyst_html = _html_section(page, "s1", "s2")
    blocks = re.findall(r"<pre><code>(.*?)</code></pre>", analyst_html, flags=re.S)
    assert len(blocks) == 1, f"expected one code block, found {len(blocks)}"
    code = unescape(blocks[0])
    assert code.rstrip("\n") == "a=1\n\nb=2", f"code block is not whole: {code!r}"
    assert "FUN-" not in code, "a paragraph ID was inserted inside the code block"


def _html_section(page, start, following):
    """The HTML page between the section with id ``start`` and the next one."""
    return page.partition(f'id="{start}"')[2].partition(f'id="{following}"')[0]


def _research_prompt(state):
    """The bull prompt for ``state`` (its label text, unmodified)."""
    from tradingagents.agents.researchers.bull_researcher import create_bull_researcher

    llm = RecordingLLM()
    create_bull_researcher(llm)(dict(state))
    return llm.prompt_text


@pytest.mark.unit
def test_supp_a_debate_fence_with_blank_lines_stays_with_its_argument():
    """Finding 5: the debate fence follows the same rule — one fenced block, no
    matter what it contains, attached to the argument before it."""
    turn = "Claim [FUN-01].\n```\na=1\n\nb=2\n```\n\nNext claim."
    arguments = split_arguments(turn)

    assert [a.text for a in arguments] == [
        "Claim [FUN-01].\n```\na=1\n\nb=2\n```",
        "Next claim.",
    ], arguments

    entry = resolve_turn("bear", 1, turn, report_map())
    assert [a["note"] for a in entry["arguments"]] == ["", UNCITED]
    assert "[FUN-01]" in entry["arguments"][0]["text"]
    assert "b=2" in entry["arguments"][0]["text"]


# --- Finding 6: one turn number per speaker -------------------------------


@pytest.mark.unit
def test_supp_bull_and_bear_number_their_turns_on_the_same_scale():
    """Finding 6: each speaker's turn numbers its own utterances, so a speaker's
    first turn is turn 1 and a speaker's next turn is turn 2. Recording the bull
    as 1 and the bear as 2 from the shared count makes the two speakers
    disagree."""
    from tradingagents.agents.researchers.bear_researcher import create_bear_researcher
    from tradingagents.agents.researchers.bull_researcher import create_bull_researcher

    def run(node, text, debate):
        update = node(RecordingLLM(text))(_state(paragraphs=DEFAULT_MAP, debate=debate))
        return update["investment_debate_state"]

    def turns(debate, speaker):
        return [e["turn"] for e in debate["turn_citations"] if e["speaker"] == speaker]

    # A full second round: bull, bear, bull, bear — the bear's second turn too.
    debate = run(create_bull_researcher, "Bull claim one.", {"count": 0})
    assert turns(debate, "bull") == [1], "the bull's first turn is 1"

    debate = run(create_bear_researcher, "Bear claim one.", debate)
    assert turns(debate, "bear") == [1], (
        f"the bear's first turn is its own turn 1, not {turns(debate, 'bear')}")

    debate = run(create_bull_researcher, "Bull claim two.", debate)
    debate = run(create_bear_researcher, "Bear claim two.", debate)

    assert turns(debate, "bull") == [1, 2], turns(debate, "bull")
    assert turns(debate, "bear") == [1, 2], turns(debate, "bear")
    assert [e["speaker"] for e in debate["turn_citations"]] == ["bull", "bear", "bull", "bear"]
