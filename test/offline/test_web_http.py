"""WEB-T2/T4 over the real HTTP surface — the interface the page actually calls.

One end-to-end case drives analysis through HTTP and reads it back through HTTP:

1. ``GET /api/config`` returns the form defaults; the default-selected analysts
   include ``options`` (FEAT-01), and the models are present.
2. ``POST /api/runs`` starts a run from a submitted configuration; the running
   configuration (models + analysts) must reach the backend graph unchanged.
3. The fake graph emits one identifiable analyst event and then pauses. Polling
   ``GET /api/runs/{id}/events`` reads that exact content while the run runs;
   polling again with the returned cursor adds nothing.
4. Releasing the graph, then ``GET /api/runs/{id}/report`` (HTML) and
   ``GET /api/runs/{id}/report.md`` (download) serve this run's artifacts, and
   the whole session ran the analysis exactly once.

RunManager unit coverage keeps the finer event, failure and citation cases.

The HTTP 200 checks exercise the interface only. Tab auto-switching and
click-to-source scrolling remain browser acceptance items.
"""

from __future__ import annotations

import json
import threading
import urllib.request

import pytest

import cli.web as web


class _Gate:
    def __init__(self):
        self._released = threading.Event()

    def release(self):
        self._released.set()

    def wait(self, timeout=5.0):
        assert self._released.wait(timeout), "the test never released the paused step"


class _FakeGraph:
    """Runs one step, then pauses before the next until released; exports once."""

    def __init__(self, gate):
        self._gate = gate
        self.graph = self
        self.propagator = self
        self._resuming = False
        self.report_calls = 0
        self.stream_calls = 0
        # Set when stream_run starts, so the test can wait instead of guessing.
        self.started = threading.Event()
        # Captured by get_graph_args so the test can read what the backend got.
        self.config_seen = {}
        self.callbacks = []

    def configure(self, config):
        self.config_seen = dict(config)

    def create_run_state(self, ticker, trade_date, asset_type="stock", portfolio=None):
        return {"messages": [], "company_of_interest": ticker, "trade_date": trade_date}

    def get_graph_args(self, callbacks=None):
        self.callbacks = callbacks or []
        return {}

    def begin_checkpoint(self, *a, **k):
        return None

    def checkpoint_input(self, state):
        return state

    def end_checkpoint(self):
        pass

    def record_decision(self, *a, **k):
        pass

    def clear_checkpoint_on_success(self, *a, **k):
        pass

    def run_settings(self):
        return {"version": "test", "analysts": ["options"]}

    def _state(self):
        return {
            "company_of_interest": "NVDA",
            "trade_date": "2026-11-22",
            "company_identity": {"company_name": "NVIDIA", "industry": "Semiconductors",
                                 "business_description": "Designs GPUs."},
            "market_report": "Market body UNIQUE_MARKET_42.",
            "options_report": "Options body.",
            "investment_debate_state": {"bull_history": "", "bear_history": "",
                                        "report_paragraphs": [], "turn_citations": [],
                                        "progress_outcome": "", "progress_round": 0,
                                        "progress_reason": ""},
            "final_trade_decision": "Rating: Buy\n\nBuy NVDA.",
            "final_rating": "Buy",
        }

    def save_reports(self, final_state, ticker, save_path=None, html=True):
        from tradingagents.reporting import write_report_tree

        self.report_calls += 1
        return write_report_tree(final_state, ticker, save_path, settings=self.run_settings(), html=html)

    def stream_run(self, graph_input, **kwargs):
        from langchain_core.messages import AIMessage

        self.stream_calls += 1
        self.started.set()
        # One clearly identifiable analyst event, then pause before finishing.
        yield [AIMessage(content="UNIQUE_EVENT_42 analyst working")], {"messages": []}
        self._gate.wait()
        yield [], self._state()


def _get(url, method="GET", body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read()
        return resp.status, raw


def _json(url, method="GET", body=None):
    status, raw = _get(url, method, body)
    return status, json.loads(raw.decode("utf-8"))


@pytest.fixture
def server(monkeypatch):
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    gate = _Gate()
    graph = _FakeGraph(gate)
    monkeypatch.setattr(web, "build_graph", lambda config, callbacks=None: _graph_configured(graph, config))

    srv, thread = web.start_in_thread(host="127.0.0.1", port=port, graph_factory=None)
    base = f"http://127.0.0.1:{port}"
    try:
        yield base, graph, gate
    finally:
        web.stop(srv, thread)


def _graph_configured(graph, config):
    graph.configure(config)
    return graph


@pytest.mark.unit
@pytest.mark.loopback
def test_http_end_to_end_start_stream_report_download(server):
    base, graph, gate = server

    # 1. Configuration defaults: options is among the default-selected analysts.
    status, config = _json(f"{base}/api/config")
    assert status == 200
    assert "options" in config["analysts_default"], config
    assert config["models"], config  # quick/deep model choices are offered

    # 2. Start a run over HTTP with a non-default model/analyst selection.
    submitted = {
        "ticker": "NVDA",
        "date": "2026-11-22",
        "analysts": ["market", "options"],
        "quick_think_llm": "quick-x",
        "deep_think_llm": "deep-x",
    }
    status, started = _json(f"{base}/api/runs", method="POST", body=submitted)
    assert status in (200, 201), started
    run_id = started["run_id"]

    # 3. Poll events by cursor until the specific event is readable. This does not
    #    assume the background thread reached stream_run before the POST returned.
    events, cursor = _poll_for_event(base, run_id, "UNIQUE_EVENT_42", timeout=5.0)

    # The submitted model/analyst selection reached the backend graph config,
    # checked now that the run is demonstrably under way.
    assert graph.started.is_set()
    assert graph.config_seen.get("quick_think_llm") == "quick-x"
    assert graph.config_seen.get("deep_think_llm") == "deep-x"
    assert list(graph.config_seen.get("selected_analysts") or graph.config_seen.get("analysts")) == ["market", "options"]

    # The run is still paused (the second step waits for the gate).
    status, snap = _json(f"{base}/api/runs/{run_id}/status")
    assert status == 200
    assert snap["state"] == "running"

    # Polling again from the returned cursor must add nothing (no duplicates).
    status, second = _json(f"{base}/api/runs/{run_id}/events?since={cursor}")
    assert status == 200
    assert second["events"] == [], second
    assert "UNIQUE_EVENT_42" not in " ".join(json.dumps(e) for e in second["events"])

    # 4. Release the graph, wait for completion, then read the report and download.
    gate.release()
    completed = _wait_status(base, run_id, "succeeded")
    assert (completed["ticker"], completed["date"], completed["rating"]) == ("NVDA", submitted["date"], "Buy")

    status, report_html = _get(f"{base}/api/runs/{run_id}/report")
    assert status == 200
    assert b"UNIQUE_MARKET_42" in report_html  # this run's content, in the preview
    assert b"Company Background" in report_html  # FEAT-03 survives into the preview

    status, md = _get(f"{base}/api/runs/{run_id}/report.md")
    assert status == 200
    assert b"UNIQUE_MARKET_42" in md
    assert b"Company Background" in md

    # The whole HTTP session ran the analysis exactly once and exported once.
    assert graph.stream_calls == 1
    assert graph.report_calls == 1


def _poll_for_event(base, run_id, needle, timeout=5.0):
    """Poll the events endpoint by cursor until ``needle`` appears; return events, next."""
    import time

    cursor = 0
    seen = []
    deadline = time.time() + timeout
    while time.time() < deadline:
        status, batch = _json(f"{base}/api/runs/{run_id}/events?since={cursor}")
        assert status == 200
        if batch["events"]:
            seen.extend(batch["events"])
            cursor = batch["next"]
        if needle in " ".join(json.dumps(e) for e in seen):
            return seen, cursor
        time.sleep(0.02)
    raise AssertionError(f"event {needle!r} not read within {timeout}s; saw {seen}")


def _wait_status(base, run_id, wanted, timeout=5.0):
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        status, snap = _json(f"{base}/api/runs/{run_id}/status")
        if snap.get("state") == wanted:
            return snap
        time.sleep(0.02)
    raise AssertionError(f"run {run_id} did not reach {wanted}")
