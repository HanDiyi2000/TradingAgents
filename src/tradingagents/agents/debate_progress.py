"""FEAT-02 / FR-DEB-01: semantic progress judgement for the bull/bear debate.

This is a leaf module: it imports only ``pydantic`` and the shared structured
helper so that both ``graph`` (the router) and ``agents`` (the bear node) can
import it without a cycle. It never imports ``tradingagents.graph``.

FR-DEB-01 says the debate ends early when neither side introduces evidence new
to this debate nor gives a first substantive reply to a previously unanswered
opposing argument. Surface heuristics (new numbers, entities, reply markers) are
not faithful to that meaning, so a structured semantic judgement decides it.
The judgement is computed once per eligible completed pair, in the bear node.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from tradingagents.agents.structured import NO_EXTERNAL_TOOLS

logger = logging.getLogger(__name__)

PROGRESS = "PROGRESS"
NO_PROGRESS = "NO_PROGRESS"
UNKNOWN = "UNKNOWN"

# The exact approved early-stop reason (FR-DEB-01 / FEAT-02 blueprint).
EARLY_STOP_REASON = "No new evidence or first response in this round"

_CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}


class _SideJudgement(BaseModel):
    new_evidence: bool = Field(
        description="True if this turn introduces a fact/observation not already "
        "present in the prior debate history, judged by meaning, whether numeric "
        "or qualitative."
    )
    first_reply: bool = Field(
        description="True if this turn gives a first substantive response to a "
        "specific opposing argument that had no prior substantive response in "
        "this history."
    )
    confidence: Literal["low", "medium", "high"] = Field(
        description="Confidence in the two booleans for this side."
    )


class DebateJudgement(BaseModel):
    """Structured judgement for one completed bull/bear pair."""

    bull: _SideJudgement
    bear: _SideJudgement
    outcome: Literal["PROGRESS", "NO_PROGRESS", "UNKNOWN"]


@dataclass(frozen=True)
class ProgressResult:
    outcome: str
    evaluated_round: int


def _flags_any_true(side) -> bool:
    return bool(side["new_evidence"] or side["first_reply"])


def classify_judgement(payload) -> str:
    """Map a structured judgement payload to PROGRESS / NO_PROGRESS / UNKNOWN.

    Deterministic; never trusts the payload's own ``outcome`` when it disagrees
    with the booleans. Missing, malformed, inconsistent or uncertain results are
    UNKNOWN (which continues the debate) — never NO_PROGRESS.
    """
    if not isinstance(payload, dict):
        return UNKNOWN

    outcome = payload.get("outcome")
    if outcome == UNKNOWN:
        return UNKNOWN

    bull = payload.get("bull")
    bear = payload.get("bear")
    if not isinstance(bull, dict) or not isinstance(bear, dict):
        return UNKNOWN
    for side in (bull, bear):
        if not all(isinstance(side.get(k), bool) for k in ("new_evidence", "first_reply")):
            return UNKNOWN
        if side.get("confidence") not in _CONFIDENCE_RANK:
            return UNKNOWN

    progress = _flags_any_true(bull) or _flags_any_true(bear)
    no_progress = not progress

    # Inconsistent: the stated outcome contradicts the booleans.
    if outcome == PROGRESS and no_progress:
        return UNKNOWN
    if outcome == NO_PROGRESS and progress:
        return UNKNOWN

    if progress:
        return PROGRESS

    # A weak negative on either side must not become a confirmed NO_PROGRESS.
    if any(_CONFIDENCE_RANK[side["confidence"]] < _CONFIDENCE_RANK["medium"]
           for side in (bull, bear)):
        return UNKNOWN

    # Confirmed repetition: all flags false, both sides medium+, outcome agrees.
    return NO_PROGRESS


class DebateJudge:
    """Invokes the quick-tier model for a structured judgement."""

    def __init__(self, llm):
        try:
            self._structured = llm.with_structured_output(DebateJudgement)
        except (NotImplementedError, AttributeError):
            self._structured = None

    def evaluate(self, prompt) -> DebateJudgement | None:
        """Run the structured judgement and return the parsed model, or None.

        Exposes the per-side fields (``bull``/``bear``) for evaluation without
        changing routing. Returns None on the same conditions ``invoke`` treats as
        a structural failure: no structured binding, or an unparseable result.
        """
        if self._structured is None:
            return None
        return self._structured.invoke(prompt)

    def invoke(self, prompt) -> ProgressResult:
        """Return a ProgressResult with the mapped outcome.

        A structural failure yields UNKNOWN. The round is tagged by the caller
        (the bear node), so it is left at 0 here. Shares the structured path with
        ``evaluate`` so both observe the same model output.
        """
        payload = self.evaluate(prompt)
        return ProgressResult(classify_judgement(_payload_to_dict(payload)), 0)


def build_debate_judge(llm) -> DebateJudge:
    """Build the judge from the existing quick-tier LLM (no new client)."""
    return DebateJudge(llm)


def evaluate_pair(judge, history: str, bull_turn: str, bear_turn: str,
                  round_number: int) -> ProgressResult:
    """Run the judge for one completed pair and tag it with the round.

    A failed or malformed judgement becomes UNKNOWN (continue); it is never
    retried as free text. Provider/SDK-level transport retries inside the client
    are not judgement attempts.
    """
    prompt = _render_prompt(history, bull_turn, bear_turn)
    try:
        result = judge.invoke(prompt)
    except Exception as exc:  # noqa: BLE001 — a broken judge must not end the run
        logger.warning("Debate progress judgement failed: %s", exc)
        return ProgressResult(UNKNOWN, round_number)

    outcome = getattr(result, "outcome", None)
    if outcome not in (PROGRESS, NO_PROGRESS, UNKNOWN):
        outcome = UNKNOWN
    return ProgressResult(outcome, round_number)


def _payload_to_dict(payload) -> dict | None:
    if payload is None:
        return None
    if isinstance(payload, dict):
        return payload
    model_dump = getattr(payload, "model_dump", None)
    if callable(model_dump):
        return model_dump()
    return None


def _render_prompt(history: str, bull_turn: str, bear_turn: str) -> str:
    return f"""You judge progress in a bull-versus-bear investment debate. One round is one bull turn and one bear turn.

Decide, for each side, whether that side's turn:
- introduced evidence NEW to this debate (a fact or observation not already present in the history), judged by meaning — a reused number that carries a different fact still counts as new; a qualitative claim with no number can be new; a fact restated with only new citation labels is not new; and
- gave a FIRST substantive response to a specific opposing argument that had NO prior substantive response in this history — a reply that merely repeats a rebuttal already made and answered is not a first reply.

Judge only against the history given. A reply is a "first reply" only if the opposing point it answers was previously unanswered in THIS history.

Prior debate history:
{history}

Current bull turn:
{bull_turn}

Current bear turn (judge it against the history plus the current bull turn):
{bear_turn}

Return for each side a boolean new_evidence, a boolean first_reply and a confidence of low, medium or high. Set outcome to PROGRESS if either side introduced new evidence or gave a first reply; otherwise NO_PROGRESS. If you cannot decide, set outcome to UNKNOWN.

{NO_EXTERNAL_TOOLS}"""
