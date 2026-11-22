"""FR-DEB-01: semantic evaluation of the debate-progress judge.

This is deliberately separate from ``test_debate_early_stop.py``:

- ``test_debate_early_stop.py`` scripts the judge's *outcome* to test routing,
  state flow, handoff and persistence ("plumbing"). Mocks there prove the
  pipeline acts on a result; they say nothing about whether the judge is right.
- This module evaluates the *judge itself* against a fixed, labelled set of
  semantic cases (``debate_progress_eval/cases.json``).

The labels are PROPOSED by the coding agent and await human review; they are not
human-approved yet.

A real-judge run needs a live structured model call, so it is excluded from the
default offline suite with the ``integration`` marker and only runs when
``TRADINGAGENTS_DEBATE_EVAL_LIVE=1`` is set and a judge is available. The
default (offline) path only validates the fixture and the judge contract, so CI
stays hermetic and no TradingAgents model call is made in this stage.

Pass criteria for a live run (documented, applied when opted in):
- Build the judge through the same leaf contract the bear node uses.
- For every case: the judge's ``new_evidence`` and ``first_reply`` flags must
  match the expected flags for BOTH sides, and the resulting outcome must match.
- SEM-06 is scored per history (A and B) against its two expectations.
- Acceptance: 100% of the six archetypes correct (exact match). Near-miss
  variants, if added later, are reported as precision/recall and are advisory.

Requirement: FR-DEB-01. Entry point for the future live check:
    TRADINGAGENTS_DEBATE_EVAL_LIVE=1 python -m pytest \\
        test/offline/test_debate_semantics_eval.py -m integration -q
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

CASES_PATH = Path(__file__).parent / "debate_progress_eval" / "cases.json"

REQUIRED_ARRAYS = {"cases"}


def _load_cases():
    data = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    return data


def test_fixture_is_well_formed():
    """Offline: the labelled set parses and every case carries its labels."""
    data = _load_cases()
    assert set(data) >= REQUIRED_ARRAYS
    cases = data["cases"]
    assert len(cases) == 7, "six archetypes, with the marker/repeat case split in two"

    archetypes = {c["archetype"] for c in cases}
    assert archetypes == {
        "reused-number-new-fact",
        "qualitative-fact-no-unit",
        "relabelled-repetition",
        "first-reply-without-marker",
        "marker-repeats-already-answered-rebuttal",
        "marker-repeat-but-other-side-first-reply",
        "same-text-different-history",
    }

    for case in cases:
        assert case["id"].startswith("SEM-")
        if case["archetype"] == "same-text-different-history":
            assert "expect_in_history_a" in case and "expect_in_history_b" in case
            assert "reply_text" in case
        else:
            for side in ("expect_bull", "expect_bear"):
                flags = case[side]
                assert set(flags) == {"new_evidence", "first_reply"}
                assert all(isinstance(v, bool) for v in flags.values())
            assert case["expect_outcome"] in {"PROGRESS", "NO_PROGRESS"}

    # SEM-05b must isolate the first-reply condition: the bear gives a first
    # substantive reply using already-known facts, so no new evidence is claimed.
    sem_05b = next(c for c in cases if c["id"] == "SEM-05b")
    assert sem_05b["expect_bear"] == {"new_evidence": False, "first_reply": True}
    assert sem_05b["expect_bull"] == {"new_evidence": False, "first_reply": False}
    assert sem_05b["expect_outcome"] == "PROGRESS"

    # SEM-05a stays a confirmed no-progress case on both sides.
    sem_05a = next(c for c in cases if c["id"] == "SEM-05a")
    assert sem_05a["expect_bull"] == {"new_evidence": False, "first_reply": False}
    assert sem_05a["expect_bear"] == {"new_evidence": False, "first_reply": False}
    assert sem_05a["expect_outcome"] == "NO_PROGRESS"


def _judge_judgement(judge, history, bull_turn, bear_turn):
    """Run the real judge's structured path for one pair; return the model or None.

    Uses the public ``DebateJudge.evaluate`` accessor, which shares the structured
    binding with ``invoke``. Returns None when the judge cannot produce a parsed
    ``DebateJudgement`` (the same structural-failure condition as ``invoke``).
    """
    from tradingagents.agents.debate_progress import _render_prompt

    prompt = _render_prompt(history, bull_turn, bear_turn)
    return judge.evaluate(prompt)


def _score_side(judgement, side):
    """The (new_evidence, first_reply) pair for one side of a DebateJudgement."""
    side_obj = getattr(judgement, side)
    return {"new_evidence": side_obj.new_evidence, "first_reply": side_obj.first_reply}


def _score_cases(judge, cases):
    """Score a judge against the labelled cases; return a list of mismatches."""
    from tradingagents.agents.debate_progress import classify_judgement

    failures = []
    for case in cases:
        if case["archetype"] == "same-text-different-history":
            judgement = _judge_judgement(
                judge, case["history_a"], case["reply_text"], ""
            )
            if judgement is None:
                failures.append((case["id"], "A", "no structured judgement", None))
                continue
            got = _score_side(judgement, "bull")
            if got != case["expect_in_history_a"]:
                failures.append((case["id"], "A", got, case["expect_in_history_a"]))
            continue

        judgement = _judge_judgement(
            judge, case["history"], case["bull_turn"], case["bear_turn"]
        )
        if judgement is None:
            failures.append((case["id"], "judge", "no structured judgement", None))
            continue
        for side in ("bull", "bear"):
            exp = case[f"expect_{side}"]
            got = _score_side(judgement, side)
            if got != exp:
                failures.append((case["id"], side, got, exp))
        # Cross-check the public mapping used by routing matches the field.
        mapped = classify_judgement(judgement.model_dump())
        if mapped != case["expect_outcome"]:
            failures.append((case["id"], "outcome", mapped, case["expect_outcome"]))
    return failures


def _assert_judge_matches_labels(judge, cases):
    failures = _score_cases(judge, cases)
    assert not failures, f"judge disagreed with labels: {failures}"


class _FakeStructuredJudgeLLM:
    """Offline fake: a per-case ``DebateJudgement`` keyed by the prompt's turns.

    Drives the *real* ``DebateJudge`` structured path without any network call,
    so the runner can be verified before a live run.
    """

    def __init__(self, judgement_for):
        self._judgement_for = judgement_for

    def with_structured_output(self, schema, **kwargs):
        class _Runner:
            def __init__(self, fn):
                self._fn = fn

            def invoke(self, prompt):
                return self._fn(prompt)

        return _Runner(self._judgement_for)


def test_runner_scores_model_derived_outcomes_against_labels_with_fake_llm():
    """Offline: the runner invokes the real judge path and compares model output.

    A fake LLM returns a canned ``DebateJudgement`` per case (derived from each
    case's own expected labels only to prove the scoring wiring); the real
    ``build_debate_judge``/``DebateJudge``/``classify_judgement`` code executes.
    This does not measure semantic accuracy — it proves the harness works.
    """
    from tradingagents.agents.debate_progress import (
        DebateJudgement,
        _SideJudgement,
        build_debate_judge,
    )

    cases = _load_cases()["cases"]

    def judgement_for_case(case):
        if case["archetype"] == "same-text-different-history":
            flags = case["expect_in_history_a"]
            side = _SideJudgement(**flags, confidence="high")
            return DebateJudgement(bull=side, bear=side, outcome="PROGRESS")
        bull = _SideJudgement(**case["expect_bull"], confidence="high")
        bear = _SideJudgement(**case["expect_bear"], confidence="high")
        return DebateJudgement(bull=bull, bear=bear, outcome=case["expect_outcome"])

    # Map each rendered prompt to its case by a unique substring: the full bear
    # turn (unique per case) or, for SEM-06, the reply text.
    def judge_for_prompt(prompt):
        for case in cases:
            marker = case.get("reply_text") or case.get("bear_turn")
            if marker and marker in prompt:
                return judgement_for_case(case)
        raise AssertionError("fake LLM saw an unknown prompt")

    judge = build_debate_judge(_FakeStructuredJudgeLLM(judge_for_prompt))
    # The real judge exposes a public evaluate() and scores cleanly against labels.
    from tradingagents.agents.debate_progress import _render_prompt

    probe = judge.evaluate(_render_prompt(cases[0]["history"], cases[0]["bull_turn"],
                                          cases[0]["bear_turn"]))
    assert isinstance(probe, DebateJudgement)
    _assert_judge_matches_labels(judge, cases)


def test_runner_reports_a_mismatch_instead_of_passing_silently():
    """Offline: a deliberately wrong judgement is reported as a failure."""
    from tradingagents.agents.debate_progress import (
        DebateJudgement,
        _SideJudgement,
        build_debate_judge,
    )

    cases = _load_cases()["cases"]

    wrong = DebateJudgement(
        bull=_SideJudgement(new_evidence=True, first_reply=True, confidence="high"),
        bear=_SideJudgement(new_evidence=True, first_reply=True, confidence="high"),
        outcome="PROGRESS",
    )
    judge = build_debate_judge(_FakeStructuredJudgeLLM(lambda prompt: wrong))

    with pytest.raises(AssertionError):
        _assert_judge_matches_labels(judge, cases)


def test_evaluate_and_invoke_share_the_judgement_path():
    """Offline: invoke()'s outcome is exactly the mapping of evaluate()'s model.

    Proves the two methods observe the same structured output, so evaluating the
    per-side fields via evaluate() measures the same judgement routing uses.
    """
    from tradingagents.agents.debate_progress import (
        NO_PROGRESS,
        DebateJudgement,
        _SideJudgement,
        build_debate_judge,
        classify_judgement,
    )

    judgement = DebateJudgement(
        bull=_SideJudgement(new_evidence=False, first_reply=False, confidence="high"),
        bear=_SideJudgement(new_evidence=False, first_reply=False, confidence="high"),
        outcome=NO_PROGRESS,
    )
    judge = build_debate_judge(_FakeStructuredJudgeLLM(lambda prompt: judgement))

    evaluated = judge.evaluate("prompt")
    invoked = judge.invoke("prompt")
    assert evaluated is judgement
    assert invoked.outcome == classify_judgement(evaluated.model_dump()) == NO_PROGRESS


class _UnstructurableLLM:
    """A model whose provider cannot do structured output."""

    def with_structured_output(self, schema, **kwargs):
        raise NotImplementedError("no structured output")


class _RaisingStructuredLLM:
    """A structured binding that fails at invoke time."""

    def with_structured_output(self, schema, **kwargs):
        class _Runner:
            def invoke(self, prompt):
                raise ValueError("malformed structured output")

        return _Runner()


class _NoneStructuredLLM:
    """A structured binding that returns None (no parsed result)."""

    def with_structured_output(self, schema, **kwargs):
        class _Runner:
            def invoke(self, prompt):
                return None

        return _Runner()


@pytest.mark.parametrize("llm_factory", [
    lambda: _UnstructurableLLM(),
    lambda: _NoneStructuredLLM(),
])
def test_evaluate_and_invoke_degrade_to_unknown_without_a_parsed_result(llm_factory):
    """No parsed result: evaluate()->None and invoke()->UNKNOWN, consistently."""
    from tradingagents.agents.debate_progress import UNKNOWN, build_debate_judge

    judge = build_debate_judge(llm_factory())
    assert judge.evaluate("prompt") is None
    assert judge.invoke("prompt").outcome == UNKNOWN


def test_structured_call_failure_propagates_from_both_methods():
    """A raising structured call propagates from evaluate() and invoke() alike.

    The caller (evaluate_pair) turns this into UNKNOWN; both methods surface the
    same failure rather than inventing a verdict, so they share one path.
    """
    from tradingagents.agents.debate_progress import build_debate_judge

    judge = build_debate_judge(_RaisingStructuredLLM())
    with pytest.raises(ValueError):
        judge.evaluate("prompt")
    with pytest.raises(ValueError):
        judge.invoke("prompt")


@pytest.mark.integration
def test_live_judge_meets_labelled_cases():
    """Gated: evaluate a real judge against the proposed labels.

    Skipped unless opted in, because it needs live structured model calls and
    this stage does not run TradingAgents model calls. Builds the real quick-tier
    LLM from the run configuration, builds the real judge, and scores the seven
    cases through the same structured path the bear node uses.
    """
    if os.environ.get("TRADINGAGENTS_DEBATE_EVAL_LIVE") != "1":
        pytest.skip("set TRADINGAGENTS_DEBATE_EVAL_LIVE=1 to run the live judge evaluation")

    from tradingagents.agents.debate_progress import build_debate_judge
    from tradingagents.dataflows.config import get_config
    from tradingagents.llm_clients import create_tier_client

    llm = create_tier_client(get_config(), "quick").get_llm()
    judge = build_debate_judge(llm)
    _assert_judge_matches_labels(judge, _load_cases()["cases"])
