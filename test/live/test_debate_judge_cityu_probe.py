"""Guarded single-request probe of the DebateJudge against the CityU DeepSeek endpoint.

This is a live, network-calling test and is excluded from the default offline
suite (``integration`` marker, and it also requires an explicit opt-in). It makes
EXACTLY ONE structured-output request through the real
``tradingagents.agents.debate_progress.DebateJudge.evaluate`` path, on a known
debate example. It never runs the seven-case semantic evaluation.

Enable and run it only when you have authorised the call:

    # PowerShell (values are read from the environment; never printed)
    $env:DEEPSEEK_API_KEY = "<your CityU token>"      # your token, not shown here
    $env:TRADINGAGENTS_CITYU_PROBE = "1"
    $env:TRADINGAGENTS_CITYU_BASE_URL = "https://llm.cs.cityu.edu.hk/v1"  # optional
    & .\\.venv\\Scripts\\python.exe -m pytest `
        test/live/test_debate_judge_cityu_probe.py -m integration -q -s

Nothing here prints the API key or the base URL's credentials. On any outcome the
test prints a single, secret-free diagnostic line and asserts the selected
classification.
"""

from __future__ import annotations

import json
import os

import pytest

CITYU_BASE_URL_DEFAULT = "https://llm.cs.cityu.edu.hk/v1"
CITYU_MODEL = "CS5351/DeepSeek-V4-Flash"

# A known debate example: the bear restates a point already made and answered, so
# a correct judge should NOT mark it as new evidence or a first reply. The probe
# only checks that the call succeeded and returned a parsed DebateJudgement; it
# is not a semantic-accuracy assertion.
HISTORY = (
    "Bull Analyst: Demand is not cyclical because backlog is multi-year.\n"
    "Bear Analyst: To address your backlog point, the backlog can be cancelled."
)
BULL_TURN = "Bull Analyst: Regarding your demand point, demand is not cyclical because backlog is multi-year."
BEAR_TURN = "Bear Analyst: To address your backlog point, the backlog can be cancelled."


def _probe_enabled() -> bool:
    return os.environ.get("TRADINGAGENTS_CITYU_PROBE") == "1"


def _has_real_key() -> bool:
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    return bool(key) and key != "placeholder"


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _probe_enabled(),
                       reason="set TRADINGAGENTS_CITYU_PROBE=1 to authorise the one live call"),
    pytest.mark.skipif(not _has_real_key(),
                       reason="DEEPSEEK_API_KEY not set (or placeholder); skipping live probe"),
]


def _build_judge():
    """Real deepseek client at the CityU endpoint with bounded retries/timeout."""
    from tradingagents.agents.debate_progress import build_debate_judge
    from tradingagents.llm_clients import create_llm_client

    base_url = os.environ.get("TRADINGAGENTS_CITYU_BASE_URL", CITYU_BASE_URL_DEFAULT)
    client = create_llm_client(
        provider="deepseek",
        model=CITYU_MODEL,
        base_url=base_url,
        max_retries=0,   # exactly one HTTP attempt
        timeout=60,      # seconds; no unbounded hang
    )
    return build_debate_judge(client.get_llm())


def _classify_exception(exc: Exception) -> str:
    """Map a failure to a coarse, secret-free category."""
    name = type(exc).__name__
    text = str(exc).lower()
    if "429" in text or "rate limit" in text or "too many requests" in text:
        return "rate_limit"
    if any(t in text for t in ("401", "403", "unauthorized", "invalid api key",
                               "authentication", "permission")):
        return "auth_failure"
    if any(t in text for t in ("response_format", "json_schema", "tool_choice",
                               "structured", "not supported", "400")):
        return "unsupported_structured_output"
    if any(t in text for t in ("timeout", "timed out", "connection")):
        return "network_or_timeout"
    return f"other:{name}"


def test_cityu_single_structured_probe(capsys):
    """One structured call through DebateJudge.evaluate(); classify the outcome."""
    from tradingagents.agents.debate_progress import _render_prompt

    judge = _build_judge()
    prompt = _render_prompt(HISTORY, BULL_TURN, BEAR_TURN)

    # Exactly one network request, via the real evaluate() path.
    try:
        judgement = judge.evaluate(prompt)
    except Exception as exc:  # noqa: BLE001 — classify, never re-raise secrets
        category = _classify_exception(exc)
        diagnostic = {
            "provider": "deepseek",
            "model": CITYU_MODEL,
            "outcome": category,
            "exception_type": type(exc).__name__,
            "message_head": str(exc)[:200],
        }
        with capsys.disabled():
            print("\nCITYU_PROBE " + json.dumps(diagnostic, ensure_ascii=True))
        pytest.fail(f"probe outcome={category}; see CITYU_PROBE diagnostic above")

    if judgement is None:
        diagnostic = {
            "provider": "deepseek",
            "model": CITYU_MODEL,
            "outcome": "unsupported_structured_output",
            "detail": "evaluate() returned None (no structured binding or unparseable)",
        }
        with capsys.disabled():
            print("\nCITYU_PROBE " + json.dumps(diagnostic, ensure_ascii=True))
        pytest.fail("probe outcome=unsupported_structured_output (evaluate returned None)")

    # Parsed successfully: report only safe, non-secret fields.
    diagnostic = {
        "provider": "deepseek",
        "model": CITYU_MODEL,
        "outcome": "success",
        "bull": judgement.bull.model_dump(),
        "bear": judgement.bear.model_dump(),
        "stated_outcome": judgement.outcome,
    }
    with capsys.disabled():
        print("\nCITYU_PROBE " + json.dumps(diagnostic, ensure_ascii=True))

    # The probe validates shape, not semantic correctness of the label.
    assert judgement.bull is not None and judgement.bear is not None
    assert judgement.outcome in {"PROGRESS", "NO_PROGRESS", "UNKNOWN"}
