"""FEAT-06: run one analysis for the web page, recording an ordered event stream.

A ``RunManager`` owns at most one active analysis at a time. It builds the same
graph the CLI builds, drives the same shared interpretation of
``graph.stream_run()`` (``cli.stream``), and exposes the run as:

* an append-only ``events`` list, each item carrying a monotonic index and a
  ``kind`` (``message``, ``tool``, ``report``, ``delegate`` or ``token_warning``),
  so a poller can fetch everything after a cursor without duplicates;
* a ``state`` (``running`` / ``succeeded`` / ``failed``) with an ``error`` on
  failure;
* on success, this run's report bytes: the HTML the exporter wrote and the
  Markdown download, both read from the run's own directory.

Nothing here re-implements analysis: the graph, its report writer and the CLI's
event interpretation are reused as they are.
"""

from __future__ import annotations

import datetime as _dt
import re
import threading
import uuid
from pathlib import Path

from cli.display import ANALYST_ORDER, MessageBuffer
from cli.stream import interpret_chunk, interpret_messages, merge_trace
from tradingagents.agents.rating import run_rating
from tradingagents.dataflows.symbols import safe_ticker_component

RUNNING = "running"
SUCCEEDED = "succeeded"
FAILED = "failed"


class _EventLog:
    """An append-only list of events with a lock, shared by the run thread and pollers."""

    def __init__(self):
        self._lock = threading.Lock()
        self._events = []
        self._next = 0

    def append(self, event: dict) -> None:
        with self._lock:
            event = {**event, "index": self._next}
            self._next += 1
            self._events.append(event)

    def since(self, cursor: int) -> tuple[list[dict], int]:
        with self._lock:
            fresh = [e for e in self._events if e["index"] >= cursor]
            return fresh, self._next

    def all(self) -> list[dict]:
        with self._lock:
            return list(self._events)

    def count(self) -> int:
        with self._lock:
            return self._next


class _ObservingBuffer(MessageBuffer):
    """A ``MessageBuffer`` that also records each user-visible change as an event.

    The shared interpreter mutates the buffer exactly as for the CLI; this
    subclass only listens and appends what the page shows, in the order it
    happens.
    """

    def __init__(self, log: _EventLog):
        super().__init__(max_length=10_000)
        self._log = log

    def add_message(self, message_type, content):
        super().add_message(message_type, content)
        self._log.append({"kind": "message", "role": message_type, "text": str(content)})

    def add_tool_call(self, tool_name, args):
        super().add_tool_call(tool_name, args)
        self._log.append({"kind": "tool", "role": "Tool", "name": tool_name, "args": args})

    def update_report_section(self, section_name, content):
        previous = self.report_sections.get(section_name)
        super().update_report_section(section_name, content)
        # Cumulative snapshots repeat unchanged sections; show each once.
        if content != previous:
            self._log.append({"kind": "report", "section": section_name, "text": str(content)})

    def update_agent_status(self, agent, status):
        super().update_agent_status(agent, status)
        self._log.append({"kind": "status", "agent": agent, "status": status})

    def note(self, kind, **fields):
        self._log.append({"kind": kind, **fields})


class _Run:
    """One analysis: its thread, its event log, and the artifacts it produced."""

    def __init__(self, run_id, config, ticker, date):
        self.id = run_id
        self.config = config
        self.ticker = ticker
        self.date = date
        self.state = RUNNING
        self.error = None
        self.log = _EventLog()
        self.thread = None
        self.report_dir = None
        self.html = None
        self.markdown = None
        self.files = {}
        self._done = threading.Event()
        self._events_ready = threading.Condition(self.log._lock)

    def snapshot(self):
        return {
            "run_id": self.id,
            "state": self.state,
            "error": self.error,
            "ticker": self.ticker,
            "date": self.date,
            "events": self.log.all(),
        }


class RunManager:
    """Start, observe and collect analyses for the web page, one active at a time."""

    def __init__(self, graph_factory, results_root=None):
        self._graph_factory = graph_factory
        self._results_root = results_root
        self._lock = threading.Lock()
        self._runs = {}
        self._active = None
        self._total = 0

    # --- starting -------------------------------------------------------------

    def start(self, config: dict) -> str:
        """Start an analysis; return its id. A second start while running reuses it."""
        with self._lock:
            if self._active is not None and self._active.state == RUNNING:
                return self._active.id
            run = self._new_run(config)
            self._active = run
            self._runs[run.id] = run
            self._total += 1
        run.thread = threading.Thread(target=self._execute, args=(run,), daemon=True,
                                      name=f"web-run-{run.id}")
        run.thread.start()
        return run.id

    def _new_run(self, config: dict) -> _Run:
        ticker = config.get("ticker") or config.get("company_of_interest") or "SPY"
        date = config.get("date") or config.get("analysis_date") or _dt.date.today().isoformat()
        return _Run(uuid.uuid4().hex, dict(config), str(ticker), str(date))

    # --- executing ------------------------------------------------------------

    def _execute(self, run: _Run) -> None:
        from cli.stats_handler import StatsCallbackHandler
        from tradingagents.default_config import (
            DEFAULT_CONFIG,
            DEFAULT_TOKEN_WARNING_THRESHOLD,
        )

        config = DEFAULT_CONFIG.copy()
        config.update(self._run_config(run.config))
        threshold = config.pop("token_warning_threshold", DEFAULT_TOKEN_WARNING_THRESHOLD)

        buffer = _ObservingBuffer(run.log)

        def notify(warning):
            buffer.note("token_warning", total_tokens=warning.total_tokens,
                        threshold=warning.threshold)

        stats_handler = StatsCallbackHandler(warning_threshold=threshold, on_token_warning=notify)
        try:
            selected = self._selected(config)
            config["selected_analysts"] = selected
            graph = self._graph_factory(config, [stats_handler])

            buffer.init_for_analysis(selected)
            run.log.append({"kind": "status", "agent": "__started__", "status": RUNNING})
            run.log.append({"kind": "message", "role": "System",
                            "text": f"Selected ticker: {run.ticker}"})
            run.log.append({"kind": "message", "role": "System",
                            "text": f"Analysis date: {run.date}"})
            run.log.append({"kind": "message", "role": "System",
                            "text": f"Selected analysts: {', '.join(selected)}"})

            args = graph.propagator.get_graph_args(callbacks=[stats_handler])
            init_state = graph.create_run_state(run.ticker, run.date, config.get("asset_type", "stock"))
            trace = []
            for messages, chunk in graph.stream_run(graph.checkpoint_input(init_state), **args):
                interpret_messages(messages, buffer)
                interpret_chunk(chunk, buffer)
                if chunk is not None:
                    _emit_progress_note(chunk, buffer)
                    trace.append(chunk)

            final_state = merge_trace(trace)
            graph.record_decision(run.ticker, run.date, final_state)
            graph.clear_checkpoint_on_success(run.ticker, run.date, config.get("asset_type", "stock"))

            run_dir = self._run_directory(config, run)
            graph.save_reports(final_state, run.ticker, run_dir, html=True)
            run.report_dir = run_dir
            md_path = run_dir / "complete_report.md"
            html_path = run_dir / "complete_report.html"
            run.files = {"markdown": md_path, "html": html_path}
            run.markdown = md_path.read_text(encoding="utf-8")
            raw_html = html_path.read_text(encoding="utf-8") if html_path.exists() else ""
            # Display-only: add FEAT-05 anchors to the preview, never to the files.
            run.html = _add_citation_anchors(raw_html)
            run.rating = run_rating(final_state)
            run.state = SUCCEEDED
            run.log.append({"kind": "message", "role": "System",
                            "text": f"Completed analysis for {run.date}"})
        except Exception as exc:  # a failed run keeps its events and reports the reason
            run.error = f"{type(exc).__name__}: {exc}"
            run.state = FAILED
            run.log.append({"kind": "error", "text": run.error})
        finally:
            run._done.set()

    def _run_config(self, submitted: dict) -> dict:
        """Translate the page's submission into graph configuration fields."""
        out = {}
        for key in ("quick_think_llm", "deep_think_llm", "backend_url", "llm_provider",
                    "output_language", "research_depth", "asset_type"):
            if submitted.get(key) is not None:
                out[key] = submitted[key]
        out["token_warning_threshold"] = submitted.get("token_warning_threshold")
        if out["token_warning_threshold"] is None:
            out.pop("token_warning_threshold")
        chosen = submitted.get("analysts") or submitted.get("selected_analysts")
        if chosen is not None:
            out["selected_analysts"] = list(chosen)
        if submitted.get("research_depth") is not None:
            depth = submitted["research_depth"]
            out.setdefault("max_debate_rounds", depth)
            out.setdefault("max_risk_discuss_rounds", depth)
        return out

    def _selected(self, config: dict) -> list[str]:
        chosen = config.get("selected_analysts") or config.get("analysts")
        if not chosen:
            return list(ANALYST_ORDER)
        values = {getattr(a, "value", a) for a in chosen}
        return [a for a in ANALYST_ORDER if a in values]

    def _run_directory(self, config: dict, run: _Run) -> Path:
        root = Path(self._results_root or config.get("results_dir", "results"))
        return root / "web" / f"{safe_ticker_component(run.ticker)}_{run.id}"

    # --- observing ------------------------------------------------------------

    def run_count(self) -> int:
        with self._lock:
            return self._total

    def _get(self, run_id) -> _Run:
        run = self._runs.get(run_id)
        if run is None:
            raise KeyError(run_id)
        return run

    def snapshot(self, run_id) -> dict:
        return self._get(run_id).snapshot()

    def events_since(self, run_id, cursor: int) -> tuple[list[dict], int]:
        return self._get(run_id).log.since(int(cursor))

    def wait_for_events(self, run_id, at_least: int = 1, timeout: float = 5.0) -> list[dict]:
        """Block until the run has at least ``at_least`` events (or it is done)."""
        run = self._get(run_id)
        import time

        deadline = time.time() + timeout
        while time.time() < deadline:
            if run.log.count() >= at_least or run.state != RUNNING:
                return run.log.all()
            time.sleep(0.01)
        return run.log.all()

    def wait_until_done(self, run_id, timeout: float = 5.0) -> None:
        run = self._get(run_id)
        if not run._done.wait(timeout):
            raise TimeoutError(f"run {run_id} did not finish within {timeout}s")

    def result(self, run_id) -> dict:
        run = self._get(run_id)
        if run.state != SUCCEEDED:
            raise RuntimeError(f"run {run_id} is {run.state}, not succeeded")
        return {
            "run_id": run.id,
            "ticker": run.ticker,
            "date": run.date,
            "rating": getattr(run, "rating", ""),
            "html": run.html,
            "markdown": run.markdown,
            "files": dict(run.files),
        }

    def delete(self, run_id) -> None:
        self._runs.pop(run_id, None)


def _emit_progress_note(chunk, buffer):
    """Surface FEAT-02's recorded early-stop reason as its own activity item, once."""
    debate = chunk.get("investment_debate_state") if isinstance(chunk, dict) else None
    if not debate:
        return
    reason = (debate.get("progress_reason") or "").strip()
    if reason and getattr(buffer, "_last_progress_reason", None) != reason:
        buffer._last_progress_reason = reason
        buffer.note("delegate", role="Research Debate",
                    text=f"Debate stopped early: {reason}")


_CITE_LABEL = re.compile(r"\[([A-Z]{3}-[0-9]{2,})\]")
_P_BLOCK = re.compile(r"<p(\s[^>]*)?>(.*?)</p>", re.DOTALL)
_PARA_START = re.compile(r"^\s*\[([A-Z]{3}-[0-9]{2,})\]\s")


def _add_citation_anchors(html: str) -> str:
    """FEAT-06 display-only: make valid FEAT-05 citations jump to their paragraph.

    Each numbered source paragraph (a ``<p>`` starting ``[XXX-NN] ...``) gets an
    ``id="para-XXX-NN"``. Every other occurrence of a *valid* id becomes a link to
    it. Invalid ids (no such paragraph) and uncited text are left as written, so
    their notices stay. The saved report files are never modified; only the
    preview string returned to the page passes through here.
    """
    valid = set()
    for match in _P_BLOCK.finditer(html):
        start = _PARA_START.match(match.group(2) or "")
        if start:
            valid.add(start.group(1))
    if not valid:
        return html

    def link_ids(text):
        return _CITE_LABEL.sub(
            lambda m: f'<a class="cite" href="#para-{m.group(1)}">[{m.group(1)}]</a>'
            if m.group(1) in valid else m.group(0),
            text,
        )

    def fix_block(match):
        attrs = match.group(1) or ""
        inner = match.group(2) or ""
        start = _PARA_START.match(inner)
        if start:
            pid = start.group(1)
            # Add the id to the paragraph (unless one is already present).
            if "id=" not in attrs:
                attrs = f' id="para-{pid}"' + attrs
            # Keep the leading marker plain (no self-link); link the rest.
            head_end = start.end()
            inner = inner[:head_end] + link_ids(inner[head_end:])
        else:
            inner = link_ids(inner)
        return f"<p{attrs}>{inner}</p>"

    return _P_BLOCK.sub(fix_block, html)
