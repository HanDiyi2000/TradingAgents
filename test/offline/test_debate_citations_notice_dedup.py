"""FEAT-05: a notice the speaker wrote itself is not appended a second time.

Confirmed in the live evaluation: a model that ends an uncited block with the
notice phrase was annotated twice, e.g.

    **First, the momentum story is a one-day move.** — *No citation provided.* — *No citation provided.*

The rendered turn must carry each notice once. Only the display suffix is
suppressed; the stored record, the model's text and the validation are not
touched.
"""

import pytest

INVALID = "Invalid citation"
UNCITED = "No citation provided"

PARAGRAPHS = [
    {"id": "FUN-01", "text": "Revenue was 800 million dollars.",
     "report_key": "fundamentals_report"},
]


def _render(text):
    from tradingagents.agents.citations import render_annotated_turn, resolve_turn

    entry = resolve_turn("bear", 1, text, PARAGRAPHS)
    return entry, render_annotated_turn(entry)


@pytest.mark.unit
def test_an_echoed_uncited_notice_is_not_appended_again():
    """The live-evaluation shape: a bold heading the model itself marked."""
    entry, rendered = _render("**Heading.** — *No citation provided.*")

    assert entry["arguments"][0]["note"] == UNCITED, "validation is unchanged"
    assert rendered == "**Heading.** — *No citation provided.*"
    assert rendered.count(UNCITED) == 1


@pytest.mark.unit
def test_an_echoed_invalid_notice_is_not_appended_again():
    """The same defect applies to the invalid notice, which carries its ID."""
    entry, rendered = _render("Bad [FUN-99]. — *Invalid citation: FUN-99.*")

    argument = entry["arguments"][0]
    assert argument["note"] == INVALID
    assert [c["id"] for c in argument["citations"]] == ["FUN-99"]
    assert argument["citations"][0]["valid"] is False
    assert rendered == "Bad [FUN-99]. — *Invalid citation: FUN-99.*"
    assert rendered.count(INVALID) == 1


@pytest.mark.unit
def test_an_ordinary_notice_is_still_appended():
    """The fix must not silence notices the speaker did not write."""
    _, rendered = _render("An uncited claim.")
    assert rendered == f"An uncited claim. — *{UNCITED}.*"

    _, rendered = _render("Bad [FUN-99].")
    assert rendered == f"Bad [FUN-99]. — *{INVALID}: FUN-99.*"


@pytest.mark.unit
def test_the_notice_phrase_mid_text_does_not_suppress_the_notice():
    """Only a trailing notice counts; a mention inside the argument is prose
    and still needs its own appended notice."""
    _, rendered = _render("It said, *No citation provided*, then kept going.")
    assert rendered.endswith(f"— *{UNCITED}.*")


@pytest.mark.unit
def test_the_record_keeps_the_model_text_and_raw_is_unchanged():
    """Presentation only: the stored argument text and the raw turn are the
    model's own words, with no notice written into them."""
    text = "**Heading.** — *No citation provided.*"
    entry, _ = _render(text)
    assert entry["raw"] == text
    assert entry["arguments"][0]["text"] == text


@pytest.mark.unit
def test_rendering_the_saved_live_turn_carries_each_notice_once():
    """The reproduced live case: replaying the saved raw A/bear response must
    not double any notice."""
    import json
    from pathlib import Path

    from tradingagents.agents.citations import render_annotated_turn, resolve_turn

    saved = Path(__file__).resolve().parents[2] / (
        "docs/evaluations/feat05-live/results.json")
    if not saved.exists():
        pytest.skip("live evaluation artifact is not present")
    record = json.loads(saved.read_text())
    run = [r for r in record["runs"] if r["run"] == "A" and r["speaker"] == "bear"][0]

    entry = resolve_turn("bear", 1, run["raw_response"], run["paragraph_map"])
    rendered = render_annotated_turn(entry)

    blocks = rendered.split("\n\n")
    assert not [b for b in blocks if b.count(UNCITED) > 1], "no block is told twice"
    # The model wrote the phrase 8 times; only genuinely uncited blocks add it.
    assert rendered.count(UNCITED) - run["raw_response"].count(UNCITED) == 3
    assert [a["text"] for a in entry["arguments"]] == [
        a["text"] for a in run["arguments"]], "segmentation is unchanged"
