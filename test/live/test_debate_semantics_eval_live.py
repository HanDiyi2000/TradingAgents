"""FR-DEB-01: replay the fixed semantic cases through the real provider."""
import os

import pytest
from offline.test_debate_semantics_eval import _assert_judge_matches_labels, _load_cases

# CityU DeepSeek endpoint used for the live run (same as the guarded probe). The
# client is built directly so no TRADINGAGENTS_* provider config is required.
CITYU_BASE_URL_DEFAULT = "https://llm.cs.cityu.edu.hk/v1"
CITYU_MODEL = "CS5351/DeepSeek-V4-Flash"


def _build_cityu_judge():
    """The real judge on the CityU DeepSeek endpoint, bounded for a single run.

    Uses the existing ``deepseek`` OpenAI-compatible client (the same provider
    family the quick tier uses) pointed at the CityU base URL with the exact
    model id. This avoids relying on TRADINGAGENTS_* provider config, which
    ``test/conftest.py`` blanks. ``DEEPSEEK_API_KEY`` (no such prefix) is read by
    the client itself and is never printed here.
    """
    from tradingagents.agents.debate_progress import build_debate_judge
    from tradingagents.llm_clients import create_llm_client

    base_url = (
        os.environ.get("CITYU_BASE_URL")
        or os.environ.get("TRADINGAGENTS_CITYU_BASE_URL")  # may be blanked by conftest
        or CITYU_BASE_URL_DEFAULT
    )
    client = create_llm_client(
        provider="deepseek",
        model=CITYU_MODEL,
        base_url=base_url,
        max_retries=1,
        timeout=60,
    )
    return build_debate_judge(client.get_llm())


@pytest.mark.integration
def test_live_judge_meets_labelled_cases():
    """Gated: evaluate the real CityU judge against the proposed labels.

    Skipped unless opted in, because it makes live structured model calls. Builds
    the quick-tier-style deepseek client at the CityU endpoint with the exact model
    ``CS5351/DeepSeek-V4-Flash``, builds the real judge, and scores the seven cases
    through the same structured path the bear node uses.
    """
    if os.environ.get("DEBATE_EVAL_LIVE") != "1":
        pytest.skip("set DEBATE_EVAL_LIVE=1 to run the live judge evaluation")

    judge = _build_cityu_judge()
    _assert_judge_matches_labels(judge, _load_cases()["cases"])
