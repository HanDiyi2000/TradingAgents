"""WEB-T2/T3 · FR-WEB-02 — live events, ordering, single start, failure/retry.

The tests drive the web run manager with a *pausable* fake graph, so timing is
controlled by hand rather than by ``sleep``: the fake yields one stream step and
then blocks on an event the test releases. That proves a page can read the first
event while the run is still going, and that a repeated snapshot does not
duplicate what was already shown.

These pin the approved (not-yet-implemented) interface:

* ``cli.web.RunManager`` accepts a graph factory and a run configuration, and
  runs the same ``stream_run`` the CLI consumes.
* ``manager.snapshot(run_id)`` returns the events received so far plus the run
  state (``idle``/``running``/``succeeded``/``failed``), so a poller sees new
  events before the run ends.
* ``manager.start(config)`` starts one run; a second call while running does not
  start another.
"""

from __future__ import annotations

import threading

import pytest

from cli.web import RunManager


class _Gate:
    """A one-slot release, so a fake stream pauses where the test wants."""

    def __init__(self):
        self._released = threading.Event()

    def release(self):
        self._released.set()

    def wait(self, timeout=5.0):
        assert self._released.wait(timeout), "the test never released the paused step"


class _PausableGraph:
    """A graph whose stream blocks between steps until the test releases it.

    ``steps`` is a list of ``(messages, chunk)`` yields. ``pause_before`` maps a
    step index to a gate that must be released before that step is yielded.
    """

    def __init__(self, steps, gates=None, fail_after=None):
        self._steps = steps
        self._gates = gates or {}
        self._fail_after = fail_after

        # The lifecycle surface run_analysis uses.
        self.graph = self
        self.propagator = self
        self._resuming = False

    def create_run_state(self, ticker, trade_date, asset_type="stock", portfolio=None):
        return {"messages": [], "company_of_interest": ticker, "trade_date": trade_date}

    def get_graph_args(self, callbacks=None):
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

    def save_reports(self, final_state, ticker, save_path=None, html=True):
        from tradingagents.reporting import write_report_tree

        return write_report_tree(final_state, ticker, save_path, settings=self.run_settings(), html=html)

    def stream_run(self, graph_input, **kwargs):
        for i, (messages, chunk) in enumerate(self._steps):
            gate = self._gates.get(i)
            if gate is not None:
                gate.wait()
            if self._fail_after is not None and i == self._fail_after:
                raise RuntimeError("graph failed mid-run")
            yield messages, chunk


CONFIG = {"ticker": "NVDA", "analysis_date": "2026-11-22",
          "analysts": ["market", "options"], "asset_type": "stock"}


def _manager(graph):
    return RunManager(graph_factory=lambda *a, **k: graph, results_root=None)


@pytest.mark.unit
def test_the_first_event_is_visible_before_the_run_finishes():
    """WEB-T2: a page can read a tool call and analyst report while paused."""
    after_first = _Gate()
    steps = [
        ([_ai("Using indicators")], {"messages": []}),          # 0: message
        ([_ai("market done", tool_calls=[_tool("get_stock")])],
         {"market_report": "Market body", "messages": []}),      # 1: report + tool
        ([_ai("still working")], {"messages": []}),             # 2: gated next step
        ([_ai("decision")],
         {"final_trade_decision": "Rating: Buy\n\nBuy NVDA.", "final_rating": "Buy"}),
    ]
    graph = _PausableGraph(steps, gates={2: after_first})
    manager = _manager(graph)

    run_id = manager.start(CONFIG)

    # Block until at least one event is visible, without guessing with sleep.
    events = manager.wait_for_events(run_id, at_least=1, timeout=5.0)
    assert events, "no event was published before the run finished"
    # The run is still running: the gated step 2 has not been released.
    assert manager.snapshot(run_id)["state"] == "running"

    # Release the rest and let it finish.
    after_first.release()
    manager.wait_until_done(run_id, timeout=5.0)
    snap = manager.snapshot(run_id)
    assert snap["state"] == "succeeded"
    kinds = [e["kind"] for e in snap["events"]]
    assert any(k in ("message", "tool") for k in kinds)


@pytest.mark.unit
def test_a_repeated_snapshot_does_not_duplicate_prior_events():
    """WEB-T2: a resumed snapshot with a repeated step must add no duplicate."""
    repeat = ([_ai("market done")], {"market_report": "Market body", "messages": []})
    steps = [repeat, repeat,  # cumulative snapshot repeats itself
             ([_ai("decision")], {"final_trade_decision": "Rating: Hold\n\nHold.", "final_rating": "Hold"})]
    manager = _manager(_PausableGraph(steps))

    run_id = manager.start(CONFIG)
    manager.wait_until_done(run_id, timeout=5.0)

    events = manager.snapshot(run_id)["events"]
    market_events = [e for e in events if e.get("section") == "market_report"]
    assert len(market_events) == 1, events


@pytest.mark.unit
def test_a_second_start_while_running_does_not_start_another_run():
    """WEB-T2/WEB-T1: only one active analysis; rapid double-submit is one run."""
    gate = _Gate()
    steps = [([_ai("a")], {"messages": []}),
             ([_ai("b")], {"market_report": "M", "messages": []}),
             ([_ai("decision")], {"final_trade_decision": "Rating: Buy\n\nB.", "final_rating": "Buy"})]
    graph = _PausableGraph(steps, gates={1: gate})
    manager = _manager(graph)

    first = manager.start(CONFIG)
    second = manager.start(CONFIG)

    assert second == first, "a second start during a run must not spawn another run"
    gate.release()
    manager.wait_until_done(first, timeout=5.0)
    # A fresh start after success is allowed and gets a new id.
    third = manager.start(CONFIG)
    manager.wait_until_done(third, timeout=5.0)
    assert third != first


@pytest.mark.unit
def test_a_failed_run_keeps_its_events_and_allows_retry():
    """WEB-T3: failure shows the reason, keeps prior events, and a retry runs anew."""
    fail_steps = [([_ai("a")], {"market_report": "Market body", "messages": []}),
                  ([_ai("boom")], {"messages": []})]
    retry_steps = [([_ai("fresh")], {"market_report": "New body", "messages": []}),
                   ([_ai("decision")], {"final_trade_decision": "Rating: Buy\n\nB.", "final_rating": "Buy"})]
    # The factory returns the failing graph first, the successful one on retry.
    graphs = [_PausableGraph(fail_steps, fail_after=1), _PausableGraph(retry_steps)]
    manager = RunManager(graph_factory=lambda *a, **k: graphs.pop(0), results_root=None)

    run_id = manager.start(CONFIG)
    manager.wait_until_done(run_id, timeout=5.0)
    snap = manager.snapshot(run_id)
    assert snap["state"] == "failed"
    assert "graph failed mid-run" in (snap.get("error") or "")
    # The report published before the failure is still readable.
    assert any(e.get("section") == "market_report" for e in snap["events"])

    # Retry after failure is allowed and gets its own id and fresh events.
    retry_id = manager.start(CONFIG)
    manager.wait_until_done(retry_id, timeout=5.0)
    assert retry_id != run_id
    retry = manager.snapshot(retry_id)
    assert retry["state"] == "succeeded"
    assert any("New body" in str(e.get("text", "")) for e in retry["events"])
    # The failing graph's content does not leak into the retry.
    assert all("Market body" not in str(e.get("text", "")) for e in retry["events"])


# --- small message helpers -------------------------------------------------------

def _ai(text, tool_calls=None):
    from langchain_core.messages import AIMessage

    return AIMessage(content=text, tool_calls=tool_calls or [])


def _tool(name):
    return {"name": name, "args": {"symbol": "NVDA"}, "id": f"call-{name}"}
