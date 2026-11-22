"""FEAT-05 rendering/segmentation regressions found in implementation review.

A small, test-only patch. The three approved files —
``test_debate_citations.py``, ``test_debate_citations_exports.py`` and
``test_debate_citations_supplementary.py`` — are unchanged and keep their hashes.

Each case below reproduces a defect that the approved tests did not catch:

1. A leading heading consumes a numbered entry in the rendered report, so the
   next block is emitted twice (once under its ID and once as unlabelled text).
2. A fence that opens directly under prose absorbs that prose, so the paragraph
   disappears from the map.
3. A debate fence that opens directly under a claim becomes its own argument
   instead of attaching to the claim.

Nothing here is a pass until it runs against the corrected implementation.
"""

from __future__ import annotations

import pytest

from tradingagents.agents.citations import (
    build_report_paragraphs,
    render_numbered_report,
    split_arguments,
)

INVALID = "Invalid citation"
UNCITED = "No citation provided"


def _reports(**overrides):
    """Every report empty except the ones named."""
    reports = dict.fromkeys(
        ("market_report", "sentiment_report", "news_report",
         "fundamentals_report", "options_report"), "")
    reports.update(overrides)
    return reports


def _paragraphs(report):
    return build_report_paragraphs(_reports(fundamentals_report=report))


# --- Finding 1: a heading neither takes an ID nor duplicates a body --------


@pytest.mark.unit
def test_reg_heading_before_two_paragraphs_keeps_source_order_and_no_duplicates():
    """Finding 1: the heading takes no ID but is preserved, unnumbered, and
    precedes each labelled body exactly once in source order."""
    report = "## Fundamentals\n\nFirst fact.\n\nSecond fact."
    paragraphs = _paragraphs(report)

    assert [p["text"] for p in paragraphs] == ["First fact.", "Second fact."], paragraphs
    assert [p["id"] for p in paragraphs] == ["FUN-01", "FUN-02"], paragraphs

    rendered = render_numbered_report("fundamentals_report", report, paragraphs)

    assert rendered == (
        "## Fundamentals\n\n"
        "[FUN-01] First fact.\n\n"
        "[FUN-02] Second fact."
    ), rendered
    assert rendered.count("## Fundamentals") == 1, "the heading is preserved once"
    assert "[FUN-01] ## Fundamentals" not in rendered, "a heading takes no ID"
    assert rendered.count("First fact.") == 1
    assert rendered.count("Second fact.") == 1, "a body must be rendered exactly once"
    # Source order: the heading, then its bodies.
    assert (
        rendered.index("## Fundamentals")
        < rendered.index("First fact.")
        < rendered.index("Second fact.")
    ), rendered


@pytest.mark.unit
def test_reg_heading_duplicate_does_not_reach_prompt_or_exports(tmp_path):
    """Finding 1: the heading is preserved unnumbered in the researcher prompt,
    the Markdown report and the HTML page, with each body exactly once and in
    source order."""
    from offline.test_debate_citations import RecordingLLM
    from offline.test_debate_citations_exports import (
        _export,
        _finished_state,
        _state as export_state,
    )
    from tradingagents.agents.researchers.bull_researcher import create_bull_researcher

    report = "## Fundamentals\n\nFirst fact.\n\nSecond fact."
    paragraphs = _paragraphs(report)
    texts = dict(_reports(fundamentals_report=report))

    # Researcher input: heading kept unnumbered, each body labelled once.
    llm = RecordingLLM()
    create_bull_researcher(llm)(
        export_state(texts, paragraphs=paragraphs, debate={"count": 0}))
    prompt = llm.prompt_text
    assert "## Fundamentals" in prompt, "the heading must reach the model"
    assert "[FUN-01] First fact." in prompt
    assert "[FUN-02] Second fact." in prompt
    assert prompt.count("## Fundamentals") == 1
    assert prompt.count("First fact.") == 1, "the prompt repeats a body"
    assert prompt.count("Second fact.") == 1, "the prompt repeats a body"
    assert prompt.index("## Fundamentals") < prompt.index("First fact."), "source order"

    # Both exports: the same heading, each body once, in source order.
    finished = _finished_state(dict(export_state(
        texts, paragraphs=paragraphs, debate={"count": 0})["investment_debate_state"]))
    finished.update(texts)
    markdown, page, _research = _export(finished, tmp_path)

    section = markdown.partition("## I. Analyst Team Reports")[2].partition("## II.")[0]
    assert "## Fundamentals" in section, "the heading must survive into Markdown"
    assert "[FUN-01] First fact." in section and "[FUN-02] Second fact." in section
    assert section.count("First fact.") == 1, section
    assert section.count("Second fact.") == 1, section
    assert section.index("## Fundamentals") < section.index("First fact."), "source order"
    assert section.index("First fact.") < section.index("Second fact."), "source order"

    assert "Fundamentals" in page, "the heading must survive into the HTML page"
    assert page.count("First fact.") == 1, "the HTML page repeats a body"
    assert page.count("Second fact.") == 1, "the HTML page repeats a body"
    assert page.index("Fundamentals") < page.index("First fact."), "source order"


# --- Finding 2: an opening fence does not absorb the prose above it --------


@pytest.mark.unit
def test_reg_prose_above_an_opening_fence_is_numbered_and_kept():
    """Finding 2: prose directly above an opening fence is its own paragraph and
    keeps its place; the fence follows it, unnumbered."""
    report = "Important fact.\n```\nx=1\n```\n\nNext fact."
    paragraphs = _paragraphs(report)

    assert [p["text"] for p in paragraphs] == ["Important fact.", "Next fact."], paragraphs
    assert [p["id"] for p in paragraphs] == ["FUN-01", "FUN-02"], paragraphs

    rendered = render_numbered_report("fundamentals_report", report, paragraphs)

    assert "[FUN-01] Important fact." in rendered
    assert "[FUN-02] Next fact." in rendered
    assert "```\nx=1\n```" in rendered, "the fence must be kept whole"
    assert "```" not in "".join(
        p["text"] for p in paragraphs), "a fence takes no ID"
    assert rendered.count("Important fact.") == 1
    # Source order: the prose, then the fence, then the next fact.
    assert rendered.index("Important fact.") < rendered.index("x=1")
    assert rendered.index("x=1") < rendered.index("Next fact.")


@pytest.mark.unit
def test_reg_prose_above_an_opening_fence_survives_prompt_and_exports(tmp_path):
    """Finding 2: the prompt and both exports keep the prose that precedes a
    fence, and keep the fence whole and unnumbered."""
    from offline.test_debate_citations import RecordingLLM
    from offline.test_debate_citations_exports import (
        _export,
        _finished_state,
        _state as export_state,
    )
    from tradingagents.agents.researchers.bull_researcher import create_bull_researcher

    report = "Important fact.\n```\nx=1\n```\n\nNext fact."
    paragraphs = _paragraphs(report)
    texts = dict(_reports(fundamentals_report=report))

    llm = RecordingLLM()
    create_bull_researcher(llm)(
        export_state(texts, paragraphs=paragraphs, debate={"count": 0}))
    prompt = llm.prompt_text
    assert "[FUN-01] Important fact." in prompt, "the prose above the fence was lost"
    assert "[FUN-02] Next fact." in prompt
    assert "```\nx=1\n```" in prompt
    assert prompt.count("```") == 2, "the fence stays one pair, unnumbered"

    finished = _finished_state(dict(export_state(
        texts, paragraphs=paragraphs, debate={"count": 0})["investment_debate_state"]))
    finished.update(texts)
    markdown, page, _research = _export(finished, tmp_path)

    section = markdown.partition("## I. Analyst Team Reports")[2].partition("## II.")[0]
    assert "[FUN-01] Important fact." in section
    assert "```\nx=1\n```" in section
    assert "[FUN-02] Next fact." in section
    assert section.count("Important fact.") == 1
    assert page.count("Important fact.") == 1
    assert "x=1" in page


# --- Finding 3: a debate fence attaches to the claim above it --------------


@pytest.mark.unit
def test_reg_a_debate_fence_directly_under_a_claim_attaches_to_it():
    """Finding 3: a fence that opens directly under a claim is part of that
    claim's argument, not a separate argument."""
    turn = "Claim [FUN-01].\n\n```\nx=1\n```"
    arguments = split_arguments(turn)

    assert [a.text for a in arguments] == [
        "Claim [FUN-01].\n\n```\nx=1\n```",
    ], arguments


@pytest.mark.unit
def test_reg_a_debate_fence_under_a_claim_takes_the_claims_notice():
    """Finding 3: attachment decides the notice. The claim's citation governs
    the whole argument, so the attached fence takes no notice of its own."""
    from tradingagents.agents.citations import render_annotated_turn, resolve_turn

    turn = "Claim [FUN-01].\n\n```\nx=1\n```"
    entry = resolve_turn("bear", 1, turn, _paragraphs("First fact."))

    assert len(entry["arguments"]) == 1, entry["arguments"]
    argument = entry["arguments"][0]
    assert [c["id"] for c in argument["citations"]] == ["FUN-01"]
    # FUN-01 is in this fixture's map ("First fact."), so the claim is valid
    # and no notice is raised for the whole argument.
    assert argument["citations"][0]["valid"] is True
    assert argument["note"] == "", "a valid claim takes no notice"

    rendered = render_annotated_turn(entry)
    assert "x=1" in rendered, "the attached fence stays with the claim"
    assert INVALID not in rendered, "a valid claim must not be flagged invalid"
    assert UNCITED not in rendered, "the fence must not take its own notice"


@pytest.mark.unit
def test_reg_a_debate_fence_still_attaches_after_a_blank_line_between():
    """Finding 3 contrast: a fence attached under its claim with no blank line
    and one separated by a blank line each yield one argument preserving its own
    exact input, and both resolve the same FUN-01 citation identically."""
    from tradingagents.agents.citations import resolve_turn

    attached = "Claim [FUN-01].\n```\nx=1\n```"
    separated = "Claim [FUN-01].\n\n```\nx=1\n```"
    paragraphs = _paragraphs("First fact.")

    assert [a.text for a in split_arguments(attached)] == [attached]
    assert [a.text for a in split_arguments(separated)] == [separated]

    first = resolve_turn("bear", 1, attached, paragraphs)["arguments"]
    second = resolve_turn("bear", 1, separated, paragraphs)["arguments"]
    assert len(first) == len(second) == 1

    # The same citation, validity and notice in both spacing variants.
    assert first[0]["citations"] == second[0]["citations"]
    assert [c["id"] for c in first[0]["citations"]] == ["FUN-01"]
    assert first[0]["citations"][0]["valid"] is True
    assert first[0]["note"] == second[0]["note"] == ""
