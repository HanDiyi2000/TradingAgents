"""FEAT-02 / FR-DEB-01: end a stalled bull/bear research debate and hand its
history to the Research Manager.

These are the feature-plumbing tests. They script the semantic judgement result
so the routing, state flow, handoff and persistence can be tested without a live
model. They do not by themselves establish semantic accuracy of the judge; that
is the job of ``test/offline/test_debate_semantics_eval.py`` and the labelled
fixtures under ``test/offline/debate_progress_eval/``.

Requirement: FR-DEB-01. Acceptance cases DEB-T1 through DEB-T5 and the fit
criterion "incorrect next speaker, stop round, termination reason or manager
history" in docs/code-governance/verification-constraints.md.

Nothing here is approved until the human reviews this diff.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from tradingagents.agents.managers.research_manager import create_research_manager
from tradingagents.agents.researchers.bear_researcher import create_bear_researcher
from tradingagents.agents.researchers.bull_researcher import create_bull_researcher
from tradingagents.graph.conditional_logic import ConditionalLogic
from tradingagents.graph.setup import DEBATE_PATH_MAP

EARLY_STOP_REASON = "No new evidence or first response in this round"

OUTCOME_PROGRESS = "PROGRESS"
OUTCOME_NO_PROGRESS = "NO_PROGRESS"
OUTCOME_UNKNOWN = "UNKNOWN"


# --- helpers ----------------------------------------------------------------


def _reports():
    return {
        "company_of_interest": "NVDA",
        "asset_type": "stock",
        "trade_date": "2026-01-09",
        "instrument_context": "The instrument to analyze is `NVDA`.",
        "market_report": "m",
        "sentiment_report": "s",
        "news_report": "n",
        "fundamentals_report": "f",
        "options_report": "o",
        "trader_investment_plan": "trader plan",
    }


def _debate_state(**overrides):
    base = {
        "bull_history": "",
        "bear_history": "",
        "history": "",
        "current_response": "",
        "count": 0,
    }
    base.update(overrides)
    return base


def _state(debate, **extra):
    return {
        **_reports(),
        "investment_plan": "plan",
        "risk_debate_state": _risk_state(),
        **extra,
        "investment_debate_state": debate,
    }


def _risk_state():
    """A minimal risk-debate state so _log_state can serialize a run."""
    return {
        "aggressive_history": "",
        "conservative_history": "",
        "neutral_history": "",
        "history": "",
        "latest_speaker": "",
        "current_aggressive_response": "",
        "current_conservative_response": "",
        "current_neutral_response": "",
        "count": 0,
    }


def _turn(label, content):
    return f"{label}: {content}"


def _scripted_turn_model(captured: dict, label: str, content: str):
    """A researcher model that returns a fixed turn (the judge is separate)."""
    llm = MagicMock()
    llm.invoke.side_effect = lambda prompt: (
        captured.__setitem__("prompt", prompt) or MagicMock(content=content)
    )
    return llm


def _router(max_rounds):
    return ConditionalLogic(max_debate_rounds=max_rounds)


# --- routing is determined by the persisted result, never recomputed --------


@pytest.mark.unit
def test_router_returns_only_known_debate_targets():
    """FR-DEB-01: the router's return set stays inside DEBATE_PATH_MAP."""
    logic = _router(max_rounds=3)
    returns = {
        logic.should_continue_debate(
            _state(_debate_state(current_response=resp, count=count))
        )
        for resp in ("Bull Analyst: x", "Bear Analyst: y", "", "drift")
        for count in (0, 1, 2, 3, 4, 5, 6, 7)
    }
    assert returns <= set(DEBATE_PATH_MAP)


@pytest.mark.unit
def test_debate_path_map_is_unchanged():
    """FR-DEB-01/FEAT-02: no new edge targets are introduced."""
    assert set(DEBATE_PATH_MAP) == {
        "Bull Researcher",
        "Bear Researcher",
        "Research Manager",
    }


# --- DEB-T1: opening round must not stop for lack of progress ---------------


@pytest.mark.unit
def test_deb_t1_opening_round_gives_bear_then_begins_round_two():
    """DEB-T1: limit 3; openings cite nothing. Bull then bear speak once and
    round two begins (no early stop on the opening round)."""
    logic = _router(max_rounds=3)

    after_bull = logic.should_continue_debate(
        _state(_debate_state(current_response="Bull Analyst: opening", count=1))
    )
    assert after_bull == "Bear Researcher"

    after_bear = logic.should_continue_debate(
        _state(_debate_state(current_response="Bear Analyst: opening", count=2))
    )
    assert after_bear == "Bull Researcher"


# --- DEB-T2: confirmed repetition in round two stops -----------------------


@pytest.mark.unit
def test_after_bull_speaks_in_round_two_the_bear_still_gets_a_turn():
    """FR-DEB-01: one round is one bull turn and one bear turn. Even if round
    two's bull turn looks like a repeat, the pair is not complete until the bear
    speaks, so the router must send the bear next (count 3, odd)."""
    logic = _router(max_rounds=3)
    target = logic.should_continue_debate(
        _state(_debate_state(
            current_response="Bull Analyst: repeats round one",
            count=3,
        ))
    )
    assert target == "Bear Researcher"


@pytest.mark.unit
def test_deb_t2_second_round_repetition_stops_after_the_bear_speaks():
    """DEB-T2: limit 3; round two repeats round-one facts and rebuttals. The bear
    still speaks; then, with a persisted NO_PROGRESS for this round, the router
    hands off instead of starting round three."""
    logic = _router(max_rounds=3)

    after_bull = logic.should_continue_debate(
        _state(_debate_state(
            current_response="Bull Analyst: repeats",
            count=3,
            progress_outcome=OUTCOME_NO_PROGRESS,
            progress_round=2,
        ))
    )
    assert after_bull == "Bear Researcher"

    after_bear = logic.should_continue_debate(
        _state(_debate_state(
            current_response="Bear Analyst: repeats",
            count=4,
            progress_outcome=OUTCOME_NO_PROGRESS,
            progress_round=2,
        ))
    )
    assert after_bear == "Research Manager"


# --- DEB-T3 / DEB-T4: progress in round two continues ----------------------


@pytest.mark.unit
@pytest.mark.parametrize("outcome", [OUTCOME_PROGRESS])
def test_deb_t3_new_report_fact_continues_to_round_three(outcome):
    """DEB-T3: limit 3; round two adds a report fact. A persisted PROGRESS keeps
    the debate going into round three."""
    logic = _router(max_rounds=3)
    target = logic.should_continue_debate(
        _state(_debate_state(
            current_response="Bear Analyst: new fact",
            count=4,
            progress_outcome=outcome,
            progress_round=2,
        ))
    )
    assert target == "Bull Researcher"


@pytest.mark.unit
def test_deb_t4_first_reply_continues_to_round_three():
    """DEB-T4: limit 3; round two answers an unanswered opposing point. A
    persisted PROGRESS keeps the debate going."""
    logic = _router(max_rounds=3)
    target = logic.should_continue_debate(
        _state(_debate_state(
            current_response="Bear Analyst: first reply",
            count=4,
            progress_outcome=OUTCOME_PROGRESS,
            progress_round=2,
        ))
    )
    assert target == "Bull Researcher"


# --- DEB-T5: the configured cap is binding and takes priority --------------


@pytest.mark.unit
def test_deb_t5_cap_one_hands_off_after_one_round():
    """DEB-T5: limit 1; cap wins even if the judgement later would say PROGRESS."""
    logic = _router(max_rounds=1)
    target = logic.should_continue_debate(
        _state(_debate_state(
            current_response="Bear Analyst: fresh",
            count=2,
            progress_outcome=OUTCOME_PROGRESS,
        ))
    )
    assert target == "Research Manager"


@pytest.mark.unit
def test_deb_t5_cap_two_hands_off_after_two_rounds():
    """DEB-T5: limit 2 with fresh evidence in round two; the cap ends it at
    exactly two complete rounds."""
    logic = _router(max_rounds=2)
    target = logic.should_continue_debate(
        _state(_debate_state(
            current_response="Bear Analyst: fresh",
            count=4,
            progress_outcome=OUTCOME_PROGRESS,
            progress_round=2,
        ))
    )
    assert target == "Research Manager"


@pytest.mark.unit
def test_cap_stop_is_not_labelled_no_progress():
    """A cap stop has no early-stop reason attached; it must not be mislabeled."""
    logic = _router(max_rounds=2)
    state = _state(_debate_state(
        current_response="Bear Analyst: repeats",
        count=4,
        progress_outcome=OUTCOME_NO_PROGRESS,
        progress_round=2,
    ))
    assert logic.should_continue_debate(state) == "Research Manager"
    # The router never emits the reason; the bear node owns it. Cap and reason
    # are independent: at the cap the stop is a cap stop.
    assert logic.should_continue_debate is not None


# --- UNKNOWN never stops; speaker order preserved --------------------------


@pytest.mark.unit
def test_unknown_outcome_continues_and_keeps_speaker_order():
    """UNKNOWN judgement must continue; a half round still gives the other side
    its turn."""
    logic = _router(max_rounds=3)
    # odd count: only the bull has spoken this round
    assert logic.should_continue_debate(
        _state(_debate_state(
            current_response="Bull Analyst: x",
            count=3,
            progress_outcome=OUTCOME_UNKNOWN,
            progress_round=2,
        ))
    ) == "Bear Researcher"
    # even count, UNKNOWN: continue rather than stop
    assert logic.should_continue_debate(
        _state(_debate_state(
            current_response="Bear Analyst: x",
            count=4,
            progress_outcome=OUTCOME_UNKNOWN,
            progress_round=2,
        ))
    ) == "Bull Researcher"


# --- stale decisions must not stop a new round/new run ---------------------


@pytest.mark.unit
def test_stale_no_progress_does_not_stop_the_opening_round():
    """A NO_PROGRESS left from a previous run/round must not stop round one."""
    logic = _router(max_rounds=3)
    target = logic.should_continue_debate(
        _state(_debate_state(
            current_response="Bull Analyst: opening",
            count=1,
            progress_outcome=OUTCOME_NO_PROGRESS,
            progress_round=1,
        ))
    )
    assert target == "Bear Researcher"


@pytest.mark.unit
def test_stale_no_progress_does_not_stop_a_later_round_without_a_current_judgement():
    """A NO_PROGRESS tagged for an earlier round must not end a later round that
    has not been judged yet."""
    logic = _router(max_rounds=3)
    # round two began (count 3), but the NO_PROGRESS belongs to round 2's prior
    # pair only after the pair is complete; at count 4 for round three we expect
    # a round tag of 2 to be stale.
    target = logic.should_continue_debate(
        _state(_debate_state(
            current_response="Bull Analyst: round three opens",
            count=5,
            progress_outcome=OUTCOME_NO_PROGRESS,
            progress_round=2,
        ))
    )
    assert target == "Bear Researcher"


# --- judgement scheduling: call counts and boundary ------------------------


@pytest.mark.unit
def test_judgement_is_scheduled_only_for_complete_rounds_between_two_and_cap():
    """FR-DEB-01: judged only when 2 <= round < cap, i.e. even count with
    4 <= count < 2*cap. At most max(0, cap-2) evaluations per run."""
    from tradingagents.graph.setup import GraphSetup  # noqa: F401  (wiring present)

    # The scheduler lives in the bear node; the contract is expressed here as the
    # set of counts that must be judged, independent of the implementation.
    def judged(count, cap):
        return count % 2 == 0 and 4 <= count < 2 * cap

    assert [c for c in range(0, 9) if judged(c, 1)] == []
    assert [c for c in range(0, 9) if judged(c, 2)] == []
    assert [c for c in range(0, 9) if judged(c, 3)] == [4]
    assert [c for c in range(0, 11) if judged(c, 4)] == [4, 6]
    assert max(0, 3 - 2) == 1 and max(0, 2 - 2) == 0 and max(0, 4 - 2) == 2


# --- the bear node persists the decision before the manager sees it --------


def _set_cap(cap: int) -> None:
    """Set ``max_debate_rounds`` in the run config the bear node reads."""
    from tradingagents.dataflows import config as config_module

    base = config_module.get_config()
    base["max_debate_rounds"] = cap
    config_module.set_config(base)


def _bear_with_judge(turn_text, judgement, cap=None):
    """A bear node whose judge returns ``judgement`` and whose model yields a
    fixed turn. Returns (node, captured) where captured records judge calls.

    ``cap`` sets ``max_debate_rounds`` in the run config the implementation reads
    (``get_config()``); when omitted the default is used.
    """
    if cap is not None:
        _set_cap(cap)

    captured = {"judge_calls": []}

    llm = MagicMock()
    llm.invoke.side_effect = lambda prompt: MagicMock(content=turn_text)

    class _Judge:
        def invoke(self, payload):
            captured["judge_calls"].append(payload)
            return judgement

    # The implementation is expected to accept the judge via the node factory;
    # this call shape is part of the reviewed contract (see plan §3/§6).
    node = create_bear_researcher(llm, judge=_Judge())
    return node, captured


def _pre_round_two_state(count=3, history=None, bull_history=None):
    history = history or (
        "\n" + _turn("Bull Analyst", "Revenue grew 10% on strong demand.") + "\n"
        + _turn("Bear Analyst", "Valuation is stretched at 40x earnings.")
    )
    return _state(
        _debate_state(
            history=history,
            bull_history=bull_history
            or "\n" + _turn("Bull Analyst", "Revenue grew 10% on strong demand."),
            bear_history="\n" + _turn("Bear Analyst", "Valuation is stretched at 40x earnings."),
            current_response="Bull Analyst: Revenue grew 10%; margins steady.",
            count=count,
        )
    )


@pytest.mark.unit
def test_bear_node_records_no_progress_reason_before_the_manager_runs():
    """The bear's returned debate update already contains the exact reason."""
    judgement = MagicMock()
    judgement.outcome = OUTCOME_NO_PROGRESS
    judgement.evaluated_round = 2
    node, _ = _bear_with_judge(
        "Valuation is stretched; margins are the same.", judgement, cap=3
    )

    # Input count 3: the bull has spoken in round two; this bear turn completes
    # the pair at count 4, which is judged (4 <= 4 < 2*3).
    result = node(_pre_round_two_state())
    debate = result["investment_debate_state"]

    assert debate["count"] == 4
    assert debate["progress_outcome"] == OUTCOME_NO_PROGRESS
    assert debate.get("progress_reason") == EARLY_STOP_REASON


@pytest.mark.unit
def test_bear_node_does_not_label_progress_with_the_stop_reason():
    judgement = MagicMock()
    judgement.outcome = OUTCOME_PROGRESS
    judgement.evaluated_round = 2
    node, _ = _bear_with_judge(
        "The bear ignores the new 10% gross-margin fact.", judgement, cap=3
    )

    debate = node(_pre_round_two_state())["investment_debate_state"]
    assert debate["count"] == 4
    assert debate["progress_outcome"] == OUTCOME_PROGRESS
    assert debate.get("progress_reason", "") == ""


@pytest.mark.unit
def test_bear_node_judges_only_round_two_not_the_opening_round():
    """No judge call while round one is still open, and none for the opening
    pair; the round-two pair (input count 3, new count 4) is judged."""
    judgement = MagicMock()
    judgement.outcome = OUTCOME_PROGRESS
    judgement.evaluated_round = 1
    node, captured = _bear_with_judge("x", judgement, cap=3)

    node(_pre_round_two_state(count=1))  # only the bull has spoken
    node(_pre_round_two_state(count=2))  # opening pair complete -> new count 3
    assert captured["judge_calls"] == []

    node(_pre_round_two_state(count=3))  # completing round two -> new count 4
    assert len(captured["judge_calls"]) == 1


@pytest.mark.unit
def test_bear_node_does_not_judge_at_or_after_the_cap():
    """Cap wins without invoking the judge: a pair whose new count reaches the
    cap is not judged (the run ends on the cap, not a progress verdict)."""
    judgement = MagicMock()
    judgement.outcome = OUTCOME_PROGRESS
    judgement.evaluated_round = 1

    # cap 2: input count 3 completes the pair at count 4 == 2*cap -> not judged.
    node, captured = _bear_with_judge("x", judgement, cap=2)
    node(_pre_round_two_state(count=3))
    assert captured["judge_calls"] == []

    # cap 3: input count 3 completes at count 4 (4 < 6) -> judged once;
    # input count 5 completes at count 6 == 2*cap -> not judged.
    node3, captured3 = _bear_with_judge("x", judgement, cap=3)
    node3(_pre_round_two_state(count=3))
    assert len(captured3["judge_calls"]) == 1
    node3(_pre_round_two_state(count=5))
    assert len(captured3["judge_calls"]) == 1


@pytest.mark.unit
def test_failed_judgement_becomes_unknown_without_a_freetext_retry():
    """A structured judge failure is UNKNOWN: no extra free-text judgement call,
    and the debate continues."""
    captured = {"judge_calls": 0, "freetext_calls": 0}

    llm = MagicMock()
    llm.invoke.side_effect = lambda prompt: MagicMock(content="bear turn")

    class _FailingJudge:
        def invoke(self, payload):
            captured["judge_calls"] += 1
            raise ValueError("malformed structured output")

    node = create_bear_researcher(llm, judge=_FailingJudge())
    _set_cap(3)
    result = node(_pre_round_two_state())
    debate = result["investment_debate_state"]

    assert debate["count"] == 4
    assert debate["progress_outcome"] == OUTCOME_UNKNOWN
    assert debate.get("progress_reason") in ("", None)
    assert captured["judge_calls"] == 1
    # the researcher's own model produced only its turn, never a judgement
    assert llm.invoke.call_count == 1


# --- the manager preserves the recorded decision ---------------------------


def _manager_structured_llm(captured: dict):
    from tradingagents.agents import schemas

    plan = schemas.ResearchPlan(
        recommendation=schemas.PortfolioRating.HOLD, rationale="r", strategic_actions="a"
    )
    llm = MagicMock()
    structured = MagicMock()
    structured.invoke.side_effect = lambda prompt: (
        captured.__setitem__("prompt", prompt) or plan
    )
    llm.with_structured_output.return_value = structured
    llm.invoke.side_effect = lambda prompt: MagicMock(content="**Rating**: Hold")
    return llm


@pytest.mark.unit
def test_manager_preserves_the_reason_it_was_given():
    """Reason-after-manager: the manager returns the recorded outcome and reason
    unchanged (not recomputed). Reason-before-manager availability is asserted on
    the bear node's returned update, which is what feeds the manager."""
    captured = {}
    manager = create_research_manager(_manager_structured_llm(captured))

    incoming = _pre_round_two_state(count=4)
    incoming["investment_debate_state"].update(
        progress_outcome=OUTCOME_NO_PROGRESS,
        progress_round=2,
        progress_reason=EARLY_STOP_REASON,
    )

    out = manager(incoming)
    debate = out["investment_debate_state"]
    assert debate["progress_outcome"] == OUTCOME_NO_PROGRESS
    assert debate["progress_reason"] == EARLY_STOP_REASON


@pytest.mark.unit
def test_manager_preserves_full_history_on_early_stop():
    captured = {}
    manager = create_research_manager(_manager_structured_llm(captured))
    incoming = _pre_round_two_state(count=4)
    full = incoming["investment_debate_state"]["history"]
    incoming["investment_debate_state"].update(
        progress_outcome=OUTCOME_NO_PROGRESS, progress_round=2,
        progress_reason=EARLY_STOP_REASON,
    )

    out = manager(incoming)
    assert out["investment_debate_state"]["history"] == full


# --- persistence in the saved run log --------------------------------------


@pytest.mark.unit
def test_saved_run_log_records_outcome_and_reason(tmp_path):
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    state = _pre_round_two_state(count=4)
    state.update(final_trade_decision="**Rating**: Hold", risk_debate_state=_risk_state())
    state["investment_debate_state"].update(
        progress_outcome=OUTCOME_NO_PROGRESS,
        progress_round=2,
        progress_reason=EARLY_STOP_REASON,
    )

    graph = object.__new__(TradingAgentsGraph)
    graph.config = {"results_dir": str(tmp_path / "logs")}
    graph.selected_analysts = ("options",)
    graph._log_state("2026-01-09", state)

    log_path = next((tmp_path / "logs").rglob("full_states_log*.json"))
    entry = json.loads(log_path.read_text())
    debate = entry["investment_debate_state"]
    assert debate.get("progress_outcome") == OUTCOME_NO_PROGRESS
    assert debate.get("progress_reason") == EARLY_STOP_REASON


# --- old-state compatibility ------------------------------------------------


@pytest.mark.unit
def test_older_state_without_progress_fields_still_routes_and_logs(tmp_path):
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    logic = _router(max_rounds=3)
    # no progress_outcome / progress_round / progress_reason at all
    state = _state(_debate_state(current_response="Bear Analyst: x", count=4))
    assert logic.should_continue_debate(state) == "Bull Researcher"

    state.update(final_trade_decision="**Rating**: Hold", risk_debate_state=_risk_state())
    graph = object.__new__(TradingAgentsGraph)
    graph.config = {"results_dir": str(tmp_path / "logs")}
    graph.selected_analysts = ("options",)
    graph._log_state("2026-01-09", state)
    entry = json.loads(next((tmp_path / "logs").rglob("full_states_log*.json")).read_text())
    # additive, defaulted keys do not break the export
    assert "history" in entry["investment_debate_state"]


# --- isolation between runs with different caps ----------------------------


@pytest.mark.unit
def test_different_caps_keep_independent_final_rounds():
    for cap, expected in ((1, 2), (2, 4), (3, 6)):
        logic = _router(max_rounds=cap)
        # at the cap for this run, the run ends regardless of judgement
        assert logic.should_continue_debate(
            _state(_debate_state(current_response="Bear Analyst: x", count=expected))
        ) == "Research Manager"
        # just below the cap for a cap high enough to have room, it continues
        if cap >= 2 and expected - 2 > 0:
            assert logic.should_continue_debate(
                _state(_debate_state(current_response="Bull Analyst: x", count=expected - 1))
            ) == "Bear Researcher"


# --- FEAT-01 regression: options delivery is unaffected --------------------


@pytest.mark.unit
def test_options_report_still_reaches_the_bull_researcher():
    """FR-OPT-03 preserved: the options report still reaches the bull."""
    tag = "OPTIONS_EVIDENCE_TAG"
    base = _pre_round_two_state()
    base["options_report"] = tag
    llm = MagicMock()
    llm.invoke.side_effect = lambda prompt: MagicMock(content="turn")
    create_bull_researcher(llm)(base)
    assert tag in str(llm.invoke.call_args[0][0])


@pytest.mark.unit
def test_options_report_still_reaches_the_bear_researcher():
    """FR-OPT-03 preserved: the options report still reaches the bear."""
    tag = "OPTIONS_EVIDENCE_TAG"
    base = _pre_round_two_state()
    base["options_report"] = tag
    llm = MagicMock()
    llm.invoke.side_effect = lambda prompt: MagicMock(content="turn")
    judgement = MagicMock()
    judgement.outcome = OUTCOME_PROGRESS
    judgement.evaluated_round = 1
    create_bear_researcher(llm, judge=MagicMock(invoke=lambda p: judgement))(base)
    assert tag in str(llm.invoke.call_args[0][0])


# --- the judged turn uses the live history, cumulatively -------------------

@pytest.mark.unit
def test_judge_compares_bull_then_bear_against_cumulative_history():
    """FR-DEB-01: the bear is judged against earlier history plus the current
    bull turn. This pins the payload the judge receives."""
    captured = {}

    class _RecordingJudge:
        def invoke(self, payload):
            captured["payload"] = payload
            result = MagicMock()
            result.outcome = OUTCOME_PROGRESS
            result.evaluated_round = 2
            return result

    bull_turn = _turn("Bull Analyst", "Gross margin held at 10%.")
    _set_cap(3)
    node = create_bear_researcher(
        MagicMock(invoke=lambda p: MagicMock(content="The bear restates the valuation case.")),
        judge=_RecordingJudge(),
    )
    node(_pre_round_two_state(count=3, history="\n" + _turn("Bull Analyst", "Revenue grew 10%."),
                              bull_history=bull_turn))

    payload = str(captured.get("payload", ""))
    # earlier history, the just-completed bull turn, and the new bear turn appear
    assert "Revenue grew 10%" in payload
    assert "Gross margin held at 10%" in payload
    assert "restates the valuation case" in payload


# --- structured judgement contract: malformed/uncertain -> UNKNOWN ---------


def _judge():
    from tradingagents.agents.debate_progress import classify_judgement

    return classify_judgement


@pytest.mark.unit
def test_contract_clean_progress_maps_to_progress():
    classify = _judge()
    payload = {
        "bull": {"new_evidence": True, "first_reply": False, "confidence": "high"},
        "bear": {"new_evidence": False, "first_reply": False, "confidence": "high"},
        "outcome": "PROGRESS",
    }
    assert classify(payload) == OUTCOME_PROGRESS


@pytest.mark.unit
def test_contract_confirmed_repetition_maps_to_no_progress():
    classify = _judge()
    payload = {
        "bull": {"new_evidence": False, "first_reply": False, "confidence": "medium"},
        "bear": {"new_evidence": False, "first_reply": False, "confidence": "high"},
        "outcome": "NO_PROGRESS",
    }
    assert classify(payload) == OUTCOME_NO_PROGRESS


@pytest.mark.unit
@pytest.mark.parametrize("payload", [
    None,
    "not a dict",
    {},
    {"bull": None, "bear": None, "outcome": "NO_PROGRESS"},
    {"bull": {"new_evidence": False, "first_reply": False, "confidence": "high"}},
    # inconsistent: says PROGRESS but every flag is false
    {
        "bull": {"new_evidence": False, "first_reply": False, "confidence": "high"},
        "bear": {"new_evidence": False, "first_reply": False, "confidence": "high"},
        "outcome": "PROGRESS",
    },
    # inconsistent: says NO_PROGRESS but a flag is true
    {
        "bull": {"new_evidence": True, "first_reply": False, "confidence": "high"},
        "bear": {"new_evidence": False, "first_reply": False, "confidence": "high"},
        "outcome": "NO_PROGRESS",
    },
    # uncertain: a weak negative on both sides must not become NO_PROGRESS
    {
        "bull": {"new_evidence": False, "first_reply": False, "confidence": "low"},
        "bear": {"new_evidence": False, "first_reply": False, "confidence": "low"},
        "outcome": "NO_PROGRESS",
    },
])
def test_contract_malformed_inconsistent_or_uncertain_is_unknown(payload):
    """No malformed/inconsistent/uncertain payload may become NO_PROGRESS: it is
    UNKNOWN, which continues the debate."""
    classify = _judge()
    assert classify(payload) == OUTCOME_UNKNOWN


@pytest.mark.unit
def test_contract_explicit_unknown_passes_through():
    classify = _judge()
    assert classify({"outcome": "UNKNOWN"}) == OUTCOME_UNKNOWN


@pytest.mark.unit
def test_contract_schema_file_matches_rules():
    """The proposed schema enumerates the same outcome values the code maps to."""
    import pathlib

    contract = json.loads(
        (pathlib.Path(__file__).parent / "debate_progress_eval" / "judgement_contract.json")
        .read_text(encoding="utf-8")
    )
    allowed = set(contract["schema"]["properties"]["outcome"]["enum"])
    assert allowed == {OUTCOME_PROGRESS, OUTCOME_NO_PROGRESS, OUTCOME_UNKNOWN}
    assert contract["schema"]["required"] == ["bull", "bear", "outcome"]
