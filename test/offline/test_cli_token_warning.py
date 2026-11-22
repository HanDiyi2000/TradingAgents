"""FR-TOK-01 / TOK-T1–T2: the CLI, real graph callbacks and report export."""

import io
import re
from threading import Event, Lock
from types import SimpleNamespace

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda
from rich.console import Console
from rich.live import Live

from cli import display, run
from cli.models import AnalystType
from tradingagents.agents.debate_progress import DebateJudgement
from tradingagents.default_config import build_default_config
from tradingagents.graph import trading_graph


class _Terminal(io.StringIO):
    """Record genuine Rich frames, including a refresh during a blocked model call."""

    def __init__(self):
        super().__init__()
        self.warning_visible = Event()

    def write(self, text):
        size = super().write(text)
        if re.search(r"token[^\n]*warn|warn[^\n]*token", text, re.IGNORECASE):
            self.warning_visible.set()
        return size

    def warnings(self):
        return [line for line in self.getvalue().splitlines()
                if re.search(r"token.*warn|warn.*token", line, re.IGNORECASE)]


class _UsageModel(BaseChatModel):
    tier: str
    next_usage: object

    @property
    def _llm_type(self):
        return "offline-usage-model"

    def bind_tools(self, tools, **kwargs):
        return self

    def with_structured_output(self, schema, **kwargs):
        if schema is not DebateJudgement:
            raise NotImplementedError
        side = {"new_evidence": False, "first_reply": False, "confidence": "high"}
        return self | RunnableLambda(
            lambda _: schema(bull=side, bear=side, outcome="NO_PROGRESS")
        )

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        pair = self.next_usage(self.tier, messages)
        usage = None
        if pair is not None:
            incoming, outgoing = pair
            usage = {"input_tokens": incoming, "output_tokens": outgoing,
                     "total_tokens": incoming + outgoing}
        return ChatResult(generations=[ChatGeneration(message=AIMessage(
            content="Offline evidence.\n\nRating: Buy\n\nFINAL TRANSACTION PROPOSAL: **BUY**",
            usage_metadata=usage,
        ))])


@pytest.fixture
def cli(monkeypatch):
    monkeypatch.setenv("TERM", "xterm-256color")
    terminal = _Terminal()
    console = Console(file=terminal, force_terminal=True, color_system=None, width=160, height=55)
    buffer = display.MessageBuffer()
    monkeypatch.setattr(run, "console", console)
    monkeypatch.setattr(run, "message_buffer", buffer)
    monkeypatch.setattr(display, "message_buffer", buffer)
    monkeypatch.setattr(run, "Live", lambda *a, **kw: Live(*a, console=console, **kw))
    monkeypatch.setattr(run, "unattended_gaps", lambda flags: [])
    # Replace only the identity source; use the normal graph and report writer.
    monkeypatch.setattr(trading_graph, "resolve_instrument_identity", lambda ticker: {})
    return terminal, buffer


def _run_cli(monkeypatch, tmp_path, ticker, pairs, terminal, pause_at=None):
    requested = []
    seen = {"quiet_before_calls": {}}
    handlers = []
    lock = Lock()
    monkeypatch.setattr(run, "get_user_selections", lambda flags: {
        "ticker": ticker, "analysis_date": "2026-01-09", "asset_type": "stock",
        "analysts": [AnalystType.NEWS, AnalystType.FUNDAMENTALS],
        "research_depth": 3, "llm_provider": "openai", "backend_url": None,
        "quick_think_llm": "fake-quick", "deep_think_llm": "fake-deep",
    })
    for key, path in (("results_dir", "results"), ("data_cache_dir", "cache"),
                      ("memory_log_path", "memory.md")):
        monkeypatch.setitem(run.DEFAULT_CONFIG, key, str(tmp_path / ticker / path))

    def next_usage(tier, messages):
        with lock:
            idx = len(requested)
            pair = pairs[idx] if idx < len(pairs) else (2, 1)
            requested.append((tier, pair, str(messages[0].content)))
        # The previous call has completed. Pause before this call can emit any
        # graph event and let Rich's own refresh thread render the warning.
        if idx in (2, 3):
            seen["quiet_before_calls"][idx] = not terminal.warning_visible.is_set()
        if idx == pause_at:
            seen["warning_before_next_completion"] = terminal.warning_visible.wait(timeout=1.5)
        return pair

    def client(config, tier, **kwargs):
        handlers.extend(kwargs["callbacks"])
        return SimpleNamespace(get_llm=lambda: _UsageModel(tier=tier, next_usage=next_usage, **kwargs))

    monkeypatch.setattr(trading_graph, "create_tier_client", client)
    run.run_analysis(flags={"save": True, "show": False, "html": True})
    assert handlers[0] is handlers[1]
    expected = [(0, 0) if pair is None else pair for _, pair, _ in requested]
    stats = handlers[0].get_stats()
    assert stats["llm_calls"] == len(requested)
    assert stats["tokens_in"] == sum(p[0] for p in expected)
    assert stats["tokens_out"] == sum(p[1] for p in expected)
    assert {tier for tier, _, _ in requested} == {"quick", "deep"}
    assert sum("You judge progress for one completed" in prompt
               or "You judge progress in a bull-versus-bear" in prompt
               for _, _, prompt in requested) == 1
    for suffix in ("md", "html"):
        (report,) = (tmp_path / ticker / "results").rglob(f"complete_report.{suffix}")
        assert "Portfolio Manager" in report.read_text(encoding="utf-8")
    return seen, handlers[0]


def _assert_only_warning_numbers(lines, expected):
    assert lines, "no token warning reached the terminal"
    for line in lines:
        # Allow thousands separators and Rich's border padding.
        numbers = {int(value.replace(",", "")) for value in re.findall(r"\d[\d,]*", line)}
        assert numbers == set(expected)


def test_tok_t1_warning_renders_while_next_model_call_is_pending(cli, monkeypatch, tmp_path):
    terminal, _ = cli
    monkeypatch.setenv("TRADINGAGENTS_TOKEN_WARNING_THRESHOLD", "1000")
    monkeypatch.setattr(run, "DEFAULT_CONFIG", build_default_config())
    observed, _ = _run_cli(
        monkeypatch, tmp_path, "NVDA",
        [(700, 200), (80, 20), (60, 40), (100, 100)], terminal, 3,
    )
    assert observed["quiet_before_calls"][2]
    assert observed["warning_before_next_completion"]
    _assert_only_warning_numbers(terminal.warnings(), (1100, 1000))


def test_tok_t2_sequential_runs_start_fresh_with_default_threshold(cli, monkeypatch, tmp_path):
    terminal, buffer = cli
    old_methods = (buffer.add_message, buffer.add_tool_call, buffer.update_report_section)
    # Two first-stage analysts run concurrently. The second completion may
    # arrive first, but the total is exactly 100000 before the first bull turn.
    results = []
    for ticker in ("NVDA", "AAPL"):
        terminal.seek(0)
        terminal.truncate()
        terminal.warning_visible.clear()
        observed, handler = _run_cli(
            monkeypatch, tmp_path, ticker, [(80000, 20000), (0, 0), None, (1, 0)], terminal,
        )
        methods = (buffer.add_message, buffer.add_tool_call, buffer.update_report_section)
        results.append((observed, handler, terminal.warnings(), methods))

    assert results[0][1] is not results[1][1]
    for observed, _, lines, methods in results:
        assert observed["quiet_before_calls"] == {2: True, 3: True}
        _assert_only_warning_numbers(lines, (100001, 100000))
        assert methods == old_methods
