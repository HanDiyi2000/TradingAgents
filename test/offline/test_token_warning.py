"""FR-TOK-01: offline accounting, notification and configuration contracts."""

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from threading import Barrier, Event, Thread

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from rich.console import Console

from cli.display import create_layout, render_live_layout
from cli.stats_handler import StatsCallbackHandler
from tradingagents.default_config import build_default_config
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.llm_clients.factory import build_llm_kwargs

ENV = "TRADINGAGENTS_TOKEN_WARNING_THRESHOLD"


def completion(pair):
    usage = None
    if pair is not None:
        incoming, outgoing = pair
        usage = {"input_tokens": incoming, "output_tokens": outgoing,
                 "total_tokens": incoming + outgoing}
    return LLMResult(generations=[[ChatGeneration(
        message=AIMessage(content="scripted", usage_metadata=usage),
    )]])


def test_tok_t1_keeps_first_crossing_and_notifies_once():
    """FR-TOK-01 / TOK-T1: strict threshold and immutable crossing values."""
    notifications = []
    handler = StatsCallbackHandler(
        warning_threshold=1000,
        on_token_warning=lambda event: notifications.append((event.total_tokens, event.threshold)),
    )
    for pair, total, expected in [
        ((700, 200), 900, []),
        ((80, 20), 1000, []),
        ((60, 40), 1100, [(1100, 1000)]),
        ((100, 100), 1300, [(1100, 1000)]),
    ]:
        handler.on_llm_end(completion(pair))
        stats = handler.get_stats()
        assert stats["tokens_in"] + stats["tokens_out"] == total
        assert notifications == expected
    assert handler.get_stats()["tokens_in"] == 940
    assert handler.get_stats()["tokens_out"] == 360
    assert handler.token_warning.total_tokens == 1100
    assert handler.token_warning.threshold == 1000


def test_concurrent_completions_count_once_and_notify_outside_lock():
    """FR-TOK-01: parallel callers cannot duplicate a notification or deadlock a reader."""
    ready = Barrier(8)
    notifications = []
    unlocked = []

    def receive(event):
        read = Event()

        def read_stats():
            notifications.append((event.total_tokens, handler.get_stats()["tokens_in"]))
            read.set()

        Thread(target=read_stats, daemon=True).start()
        unlocked.append(read.wait(timeout=2))

    handler = StatsCallbackHandler(warning_threshold=1000, on_token_warning=receive)
    handler.on_llm_end(completion((500, 500)))

    def finish():
        ready.wait(timeout=5)
        handler.on_llm_end(completion((1, 1)))

    with ThreadPoolExecutor(max_workers=8) as workers:
        futures = [workers.submit(finish) for _ in range(8)]
        for future in futures:
            future.result(timeout=5)

    assert unlocked == [True], "notification held the statistics lock"
    assert len(notifications) == 1
    assert notifications[0][0] == 1002
    assert 501 <= notifications[0][1] <= 508
    assert handler.get_stats()["tokens_in"] == handler.get_stats()["tokens_out"] == 508


def test_broken_receiver_does_not_abort_or_retry(caplog):
    """FR-TOK-01: a display failure preserves the snapshot and accounting."""
    attempted = []

    def broken(event):
        attempted.append(event.total_tokens)
        raise RuntimeError("receiver unavailable")

    handler = StatsCallbackHandler(warning_threshold=10, on_token_warning=broken)
    handler.on_llm_end(completion((5, 6)))
    handler.on_llm_end(completion((2, 3)))
    assert attempted == [11]
    assert handler.token_warning.total_tokens == 11
    assert handler.get_stats()["tokens_out"] == 9
    assert "receiver unavailable" in caplog.text


@pytest.mark.parametrize("value", [None, "", "1000"])
def test_threshold_configuration_is_independent_of_model_cap(monkeypatch, value):
    """FR-TOK-01: blank and unset follow existing env semantics."""
    if value is None:
        monkeypatch.delenv(ENV, raising=False)
    else:
        monkeypatch.setenv(ENV, value)
    monkeypatch.setenv("TRADINGAGENTS_MAX_TOKENS", "256")
    config = build_default_config()
    assert config["token_warning_threshold"] == (1000 if value == "1000" else 100000)
    assert config["max_tokens"] == "256"
    assert build_llm_kwargs({**config, "llm_provider": "openai"})["max_tokens"] == 256


@pytest.mark.parametrize("value", ["0", "-1", "1.5", "many", "   "])
def test_invalid_threshold_env_names_the_setting(monkeypatch, value):
    """FR-TOK-01: invalid configured values fail clearly."""
    monkeypatch.setenv(ENV, value)
    with pytest.raises(ValueError, match=ENV):
        build_default_config()


@pytest.mark.parametrize("value", [0, -1, 1.5, True, "1000"])
def test_handler_rejects_invalid_direct_threshold(value):
    """FR-TOK-01: the shared constructor accepts positive integers."""
    with pytest.raises(ValueError, match="positive integer"):
        StatsCallbackHandler(warning_threshold=value)


def test_threshold_loads_from_dotenv_at_startup(monkeypatch, tmp_path):
    """FR-TOK-01: the public startup path reads a real .env."""
    monkeypatch.delenv(ENV, raising=False)
    (tmp_path / ".env").write_text(f"{ENV}=1000\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-c",
         "from tradingagents.default_config import DEFAULT_CONFIG; "
         "print(DEFAULT_CONFIG.get('token_warning_threshold'))"],
        cwd=tmp_path, capture_output=True, text=True, check=True, timeout=10,
    )
    assert result.stdout.strip() == "1000"


def test_warning_threshold_does_not_change_checkpoint_identity(monkeypatch):
    """FR-TOK-01: changing a UI warning must preserve existing checkpoints."""
    monkeypatch.delenv(ENV, raising=False)
    graph = object.__new__(TradingAgentsGraph)
    graph.selected_analysts = ["news"]
    graph.config = build_default_config()
    graph.config.pop("token_warning_threshold", None)
    previous = graph._run_signature("stock")
    for threshold in (100000, 1000):
        graph.config["token_warning_threshold"] = threshold
        assert graph._run_signature("stock") == previous


@pytest.mark.parametrize("width", [40, 50, 80])
def test_tok_t1_live_layout_shows_both_numbers_at_any_tested_width(width):
    """FR-TOK-01 / TOK-T1: preserve both values when the alert wraps."""
    handler = StatsCallbackHandler()
    handler.on_llm_end(completion((100000, 1)))
    output = StringIO()
    console = Console(file=output, width=width, height=30)
    console.print(render_live_layout(create_layout(), handler, console))
    rendered = output.getvalue()
    assert rendered.count("Token usage warning") == 1
    assert "100,001 used" in rendered
    assert "100,000" in rendered
