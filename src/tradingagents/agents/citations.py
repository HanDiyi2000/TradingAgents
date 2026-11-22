"""FEAT-05 / FR-CIT-01: trace bull and bear arguments to numbered paragraphs.

The analysts' reports are numbered once per run, before the debate starts. Each
numbered paragraph is then shown to the researchers as ``[PREFIX-NN] text``, and
every argument a researcher writes is resolved against that same map: a written
ID is valid when this run's map holds it, and every argument carries either no
notice (its IDs all resolve), ``Invalid citation`` (an ID the map does not hold)
or ``No citation provided`` (no ID at all).

The annotations are derived from the model's text, never written into it. A
turn's record keeps ``raw`` exactly as the model wrote it and ``arguments`` as
the resolved pieces, so re-rendering a recorded turn — a resume, a re-export —
yields the same annotated text once, notices included.

This module is a leaf: it imports nothing from the rest of the package, so the
analyst and report layers never depend on the debate contract.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

# Stable display wording (approved). A notice trails its own argument.
INVALID = "Invalid citation"
UNCITED = "No citation provided"

# One prefix per supplied report, in the order the analysts are numbered.
REPORT_PREFIXES = (
    ("market_report", "MKT"),
    ("sentiment_report", "SEN"),
    ("news_report", "NWS"),
    ("fundamentals_report", "FUN"),
    ("options_report", "OPT"),
)

# A written citation label: three letters, a hyphen, two or more digits (a long
# report numbers past 99, so the width is not fixed).
_LABEL = re.compile(r"\[([A-Z]{3}-[0-9]{2,})\]")
_HEADING = re.compile(r"#{1,6}\s.*")
_FENCE = re.compile(r"^\s*(?:```|~~~)")
# A list item opening a line: a bullet or an ordered marker.
_LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")


@dataclass
class Argument:
    """One resolved argument of a debate turn."""

    text: str
    citations: list[dict[str, Any]] = field(default_factory=list)
    note: str = ""


# --- numbering the supplied reports ---------------------------------------

def build_report_paragraphs(reports: Mapping[str, str]) -> list[dict[str, Any]]:
    """Number every supplied report's paragraphs, in analyst order.

    Each non-empty report is numbered from ``01`` under its own prefix, so a map
    never depends on which other analysts ran; past ``99`` the label simply grows
    (``FUN-100``). Fenced code carries no ID. The result is a list of
    ``{"id", "source", "report_key", "text"}`` dicts.
    """
    paragraphs: list[dict[str, Any]] = []
    for key, prefix in REPORT_PREFIXES:
        for n, text in enumerate(_source_paragraphs(reports.get(key, "")), 1):
            paragraphs.append({
                "id": f"{prefix}-{n:02d}",
                "source": prefix,
                "report_key": key,
                "text": text,
            })
    return paragraphs


def _source_paragraphs(text: str) -> list[str]:
    """A report's paragraphs: blank-line blocks, headings given no ID.

    Source segmentation differs from argument segmentation: a block of adjacent
    list items is ONE paragraph here (it was written as one passage), whereas a
    debate turn splits each list item into its own argument.

    A fenced block receives no ID: it keeps whatever it contains — blank lines
    included — as one unnumbered unit, so code is never cited as evidence and
    never left half-numbered. A block that is only headings is skipped; a
    heading directly above body text contributes the body.
    """
    paragraphs = []
    for block in _blocks_outside_fences(text):
        if block["kind"] != "prose":
            continue  # fences and a heading on its own keep their place, no ID
        # Heading lines are set apart from their body, so the line-wise rule in
        # split_arguments reads a source paragraph the same way.
        body = _without_headings(block["text"])
        if body:
            paragraphs.append(body)
    return paragraphs


def _without_headings(text: str) -> str:
    """The lines of ``text`` that are not headings, once each."""
    return "\n".join(line for line in text.splitlines()
                     if line.strip() and not _HEADING.fullmatch(line.strip()))


def ends_in_heading(lines: list[str]) -> bool:
    """True when the last non-empty line of ``lines`` is a heading."""
    tail = [line for line in lines if line.strip()]
    return bool(tail) and _HEADING.fullmatch(tail[-1].strip()) is not None


def _blocks_outside_fences(text: str) -> list[dict]:
    """Split text into blank-line blocks, each reported with its kind.

    Returns ``[{"text", "kind"}]`` in order, where ``kind`` is ``"prose"``,
    ``"fence"`` or ``"heading"`` (a prose block made only of headings).

    A fence (```` ``` ```` or ``~~~``) is one unit whatever it contains — blank
    lines inside it never split it — and an opening fence with no close runs to
    the end of the text, so half-written code is never read as prose. Prose on
    the same line directly above a fence stays its own block, so a fence can
    never absorb the prose above it.
    """
    blocks: list[dict] = []
    current: list[str] = []
    fenced = False
    joined = False  # the fence directly followed the prose above (no blank line)

    def flush(kind):
        if current:
            blocks.append({"text": "\n".join(current), "kind": kind})
            current.clear()

    def prose(lines):
        """``"heading"`` for a block of only headings, else ``"prose"``."""
        if not lines or not any(line.strip() for line in lines):
            return None
        only_headings = all(
            _HEADING.fullmatch(line.strip()) for line in lines if line.strip())
        return "heading" if only_headings else "prose"

    for line in (text or "").splitlines():
        if _FENCE.match(line):
            if not fenced:
                joined = bool(current)
                if current and not ends_in_heading(current):
                    # Prose above is its own block; a heading directly above the
                    # fence stays with it instead of taking a block of its own.
                    flush(prose(current))
                fenced = True
                current.append(line)
                continue
            current.append(line)
            flush("fence")  # the closing fence ends the block
            blocks[-1]["joined"] = joined and len(blocks) > 1
            fenced = False
            joined = False
            continue
        if fenced:
            current.append(line)
            continue
        if not line.strip():
            kind = prose(current)
            if kind:
                flush(kind)
            else:
                current.clear()
            continue
        current.append(line)
    if current:
        kind = "fence" if fenced else prose(current)
        if kind:
            flush(kind)
    return blocks


# --- segmenting a debate turn ---------------------------------------------

def split_arguments(turn: str) -> list[Argument]:
    """Split a model's turn into arguments, each able to carry its own notice.

    An argument is a blank-line block, where:
      - a heading is not an argument: it names a section, and is dropped;
      - each list item (with its indented continuation) is its own argument;
      - a fenced block is not an argument: it attaches in full to the argument
        before it, or stands alone when it leads the turn, and a blank line
        inside the fence does not split it;
      - a table's rows are one argument.
    """
    arguments: list[str] = []
    for block in _blocks_outside_fences(turn):
        if block["kind"] == "heading":
            continue  # a heading names a section rather than making a claim
        if block["kind"] == "prose":
            # A heading line is dropped so it neither takes an uncited notice
            # nor splits the argument beneath it (the fence keeps its heading).
            block = {"text": _without_headings(block["text"]), "kind": "prose"}
            if not block["text"].strip():
                continue
        if block["kind"] == "fence":
            # A fence is never an argument: it attaches in full to the argument
            # before it, or leads the turn alone. A blank line between the claim
            # and its code is kept as written.
            if arguments:
                gap = "\n" if block.get("joined") else "\n\n"
                arguments[-1] = arguments[-1] + gap + block["text"].strip()
            else:
                arguments.append(block["text"].strip())
            continue
        current: list[str] = []
        for line in block["text"].splitlines():
            if not _LIST_ITEM.match(line):
                current.append(line)
                continue
            # A new list item starts its own argument.
            if current:
                arguments.append("\n".join(current).strip())
            current = [line]
        if current:
            arguments.append("\n".join(current).strip())
    return [Argument(text=text) for text in arguments if text]


def extract_citations(text: str) -> list[dict[str, Any]]:
    """Every written label in ``text``, in order, with its character position."""
    return [{"id": m.group(1), "position": m.start()}
            for m in _LABEL.finditer(text or "")]


def resolve_turn(
    speaker: str,
    turn_number: int,
    text: str,
    paragraphs: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Resolve one turn against this run's map.

    Returns a record ``{"speaker", "turn", "raw", "arguments"}``: ``raw`` is the
    model's text unchanged, and each argument carries the citations it wrote,
    their validity against the map, and one notice where one applies.
    """
    valid_ids = {paragraph["id"] for paragraph in paragraphs or ()}
    arguments = []
    for argument in split_arguments(text):
        claims = extract_citations(argument.text)
        note = ""
        if not claims:
            note = UNCITED
        for claim in claims:
            claim["valid"] = claim["id"] in valid_ids
        if any(not claim["valid"] for claim in claims):
            note = INVALID
        arguments.append({"text": argument.text, "citations": claims, "note": note})
    return {"speaker": speaker, "turn": turn_number, "raw": text, "arguments": arguments}


def notice_suffix(argument: Mapping[str, Any]) -> str:
    """The text appended to an argument for its notice, or ``""`` for none.

    An argument whose own words already end with its notice keeps that notice
    and gets no second one, so a speaker that echoes the phrase is annotated
    once. Only the suffix is suppressed: the model's text is never rewritten,
    and the stored ``note`` and ``citations`` are untouched.
    """
    note = argument.get("note") or ""
    if not note:
        return ""
    written = argument["text"].rstrip()
    if note == INVALID:
        if re.search(rf"\*{INVALID}: [^*]*\.?\*$", written):
            return ""
        ids = ", ".join(
            claim["id"] for claim in argument.get("citations", ()) if not claim["valid"])
        return f" — *{INVALID}: {ids}.*"
    if re.search(rf"\*{note}\.?\*$", written):
        return ""
    return f" — *{note}.*"


def render_annotated_turn(entry: Mapping[str, Any]) -> str:
    """The recorded turn as text: one argument per paragraph, notices in place.

    Derived from the stored records, never from text that already carries a
    notice, so rendering the same record twice cannot duplicate one.
    """
    rendered = [argument["text"] + notice_suffix(argument)
                for argument in entry.get("arguments", ())]
    if not rendered:
        return entry.get("raw", "")
    return "\n\n".join(rendered)


def reports_from_state(state) -> dict:
    """The five supplied reports from a run's state, keyed by state field."""
    return {key: state.get(key, "") for key, _prefix in REPORT_PREFIXES}


def render_numbered_report(report_key: str, text: str, paragraphs) -> str:
    """A report as the researchers read it: one ``[ID] paragraph`` per paragraph.

    Headings and fenced code keep their place in the report, whole and
    unnumbered, so the model reads the same report it would have read without
    labels and no body is duplicated. A report with no numbered paragraph is
    returned unchanged, so a deselected analyst still reads as absent rather
    than as an empty finding.
    """
    numbered = iter(p for p in paragraphs or () if p.get("report_key") == report_key)
    rendered = []
    for block in _blocks_outside_fences(text or ""):
        if block["kind"] == "heading":
            rendered.append(block["text"])  # kept, unnumbered
            continue
        if block["kind"] == "fence":
            rendered.append(block["text"])  # kept whole, unnumbered
            continue
        # A heading line is shown in place, unnumbered, ahead of its body.
        for line in block["text"].splitlines():
            if _HEADING.fullmatch(line.strip()):
                rendered.append(line.strip())
        paragraph = next(numbered, None)
        if paragraph is not None:
            rendered.append(f"[{paragraph['id']}] {paragraph['text']}")
        else:  # prose the map does not hold is kept as written
            rendered.append(block["text"])
    leftover = list(numbered)
    rendered.extend(f"[{p['id']}] {p['text']}" for p in leftover)
    return "\n\n".join(rendered) if rendered else (text or "")


def render_for_prompt(state, paragraphs) -> dict:
    """Every report as it goes into a researcher's prompt, labelled once."""
    return {key: render_numbered_report(key, state.get(key, ""), paragraphs)
            for key, _prefix in REPORT_PREFIXES}


def render_for_reader(text: str) -> str:
    """Recorded debate text as the reports show it.

    A recorded turn already holds one argument per paragraph, and a blank line
    separates paragraphs in both Markdown and HTML, so the recorded text is
    shown verbatim: each argument keeps its own citation and notice, and a
    re-export cannot duplicate one. Only stray surrounding blank lines are
    trimmed, so the turn starts with its speaker's own label.
    """
    return (text or "").strip("\n")
