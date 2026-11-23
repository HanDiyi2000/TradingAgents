"""FEAT-06 display: event-stream contract the collapsible, single-poll page relies on.

The page shows long reports and tool output collapsed, expands them on click, and
polls one request at a time by run_id + cursor. Those behaviours depend on the
event API guaranteeing:

* events arrive in a stable index order, each with its full text, so a client can
  render a preview and expand the whole thing;
* querying from a cursor never repeats events already delivered (a slow or
  repeated poll with the same cursor adds nothing);
* the final event is retrievable before the run flips to a terminal state, so the
  page can finish the last batch before switching to the report.

The static checks confirm the served page and script carry the collapse markup
and the one-request-at-a-time guard. Browser rendering and click-to-expand remain
manual acceptance items.
"""

from __future__ import annotations

import json
import socket
import urllib.request

import pytest

import cli.web as web


class _Gate:
    def __init__(self):
        import threading

        self._released = threading.Event()

    def release(self):
        self._released.set()

    def wait(self, timeout=5.0):
        assert self._released.wait(timeout), "the test never released the paused step"


LONG_REPORT = "Market analysis. " * 40  # well over the collapse threshold


class _FakeGraph:
    def __init__(self, gate):
        self._gate = gate
        self.graph = self
        self.propagator = self
        self._resuming = False
        self.callbacks = []

    def get_graph_args(self, callbacks=None):
        self.callbacks = callbacks or []
        return {}

    def create_run_state(self, ticker, trade_date, asset_type="stock", portfolio=None):
        return {"messages": [], "company_of_interest": ticker, "trade_date": trade_date}

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

    def save_reports(self, final_state, ticker, save_path=None, html=True):
        from tradingagents.reporting import write_report_tree

        return write_report_tree(final_state, ticker, save_path, settings=self.run_settings(), html=html)

    def stream_run(self, graph_input, **kwargs):
        from langchain_core.messages import AIMessage

        yield [AIMessage(content="short note")], {"messages": []}
        yield [AIMessage(content="calling tool", tool_calls=[
            {"name": "get_stock", "args": {"symbol": "NVDA"}, "id": "c1"}])], {"messages": []}
        yield [], {"market_report": LONG_REPORT, "messages": []}
        self._gate.wait()  # pause: the page is still reading while we hold the rest
        yield [], {"final_trade_decision": "Rating: Buy\n\nLAST_EVENT_MARKER buy.",
                   "final_rating": "Buy"}


def _json(url, method="GET", body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


@pytest.fixture
def server(monkeypatch):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    gate = _Gate()
    graph = _FakeGraph(gate)
    monkeypatch.setattr(web, "build_graph", lambda config, callbacks=None: graph)
    srv, thread = web.start_in_thread(host="127.0.0.1", port=port, graph_factory=None)
    try:
        yield f"http://127.0.0.1:{port}", graph, gate
    finally:
        web.stop(srv, thread)


def _start(base):
    submitted = {"ticker": "NVDA", "date": "2026-11-22", "analysts": ["market"],
                 "quick_think_llm": "q", "deep_think_llm": "d"}
    status, started = _json(f"{base}/api/runs", method="POST", body=submitted)
    assert status in (200, 201), started
    return started["run_id"]


def _read_until(base, run_id, needle, timeout=5.0):
    """Poll by cursor like the page, collecting events until ``needle`` appears."""
    import time

    cursor = 0
    collected = []
    deadline = time.time() + timeout
    while time.time() < deadline:
        _status, batch = _json(f"{base}/api/runs/{run_id}/events?since={cursor}")
        collected.extend(batch["events"])
        cursor = batch["next"]
        if needle in json.dumps(collected):
            return collected, cursor
        time.sleep(0.02)
    raise AssertionError(f"never read {needle!r}; collected {collected}")


@pytest.mark.unit
@pytest.mark.loopback
def test_events_come_in_order_with_full_text_for_expansion(server):
    base, _graph, gate = server
    run_id = _start(base)

    events, _cursor = _read_until(base, run_id, LONG_REPORT[:20])
    indexes = [e["index"] for e in events]
    assert indexes == sorted(indexes)  # stable order

    report = next(e for e in events if e.get("kind") == "report" and e.get("section") == "market_report")
    # The full text is present (the page shows a preview and expands to this).
    assert report["text"] == LONG_REPORT
    # A tool call event carries its name so the page can preview/expand it.
    tool = next(e for e in events if e.get("kind") == "tool")
    assert tool["name"] == "get_stock"
    gate.release()


@pytest.mark.unit
@pytest.mark.loopback
def test_a_repeated_cursor_read_adds_no_duplicates(server):
    """A slow poll re-issuing the same cursor must not repeat events."""
    base, _graph, gate = server
    run_id = _start(base)

    _events, cursor = _read_until(base, run_id, LONG_REPORT[:20])
    # Same cursor twice: the second read adds nothing (no duplicates).
    _s, again = _json(f"{base}/api/runs/{run_id}/events?since={cursor}")
    assert again["events"] == []
    assert again["next"] == cursor
    gate.release()


@pytest.mark.unit
@pytest.mark.loopback
def test_the_last_event_is_retrievable_before_finishing(server):
    base, _graph, gate = server
    run_id = _start(base)

    gate.release()  # let the run finish
    events, cursor = _read_until(base, run_id, "Completed analysis")
    # The completion event is the last one the page must show before switching.
    last = events[-1]
    assert "Completed analysis" in json.dumps(last), events
    # Nothing further remains after the final batch.
    _s, tail = _json(f"{base}/api/runs/{run_id}/events?since={cursor}")
    assert tail["events"] == []


@pytest.mark.unit
@pytest.mark.loopback
def test_served_page_has_collapsible_markup_and_single_poll_guard(server):
    base, _graph, gate = server

    with urllib.request.urlopen(f"{base}/", timeout=5) as resp:
        html = resp.read().decode("utf-8")
    assert 'id="events"' in html and 'id="view-progress"' in html

    with urllib.request.urlopen(f"{base}/app.js", timeout=5) as resp:
        js = resp.read().decode("utf-8")
    # Collapsible rendering and the one-request-at-a-time guard exist.
    assert "collapsible" in js and "event-body" in js
    assert "state.polling" in js  # single in-flight request guard
    assert "shouldStickToBottom" in js  # does not yank a reader who scrolled up
    gate.release()
