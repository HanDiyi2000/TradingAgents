"""WEB-T4 · FR-WEB-03 — per-run results, preview/download, switching, isolation.

Pins the approved web interface (``cli.web.RunManager``):

* On success a run exposes its ticker, analysis date, rating, the HTML preview and
  a Markdown download, all belonging to that run.
* Reading the preview or downloading after completion never starts another run.
* Two runs on the same ticker and date keep separate artifacts, distinguished by
  their ``run_id``; the factory returns successive graphs.
* The saved report files are exactly what the run's own export wrote; page
  anchors are a display-only addition and never alter the files on disk.

To avoid a second, timestamp-stamped export the fake graph captures the raw
bytes at the moment its single ``save_reports`` call writes them. The tests then
compare the on-disk files and the Markdown download against those captured bytes.
"""

from __future__ import annotations

import pytest

from cli.web import RunManager


class _Done:
    """A graph that completes immediately and exports once, capturing its bytes.

    ``captured`` holds ``{"md": bytes, "html": bytes}`` read back from the files
    the real exporter wrote, so a later assertion never re-runs the exporter.
    """

    def __init__(self, marker, rating="Buy", results_root=None):
        self._marker = marker
        self._rating = rating
        self._results_root = results_root
        self.graph = self
        self.propagator = self
        self._resuming = False
        self.report_calls = 0
        self.captured = {}

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

    def _state(self):
        # Real FEAT-05 shapes: numbered options paragraphs and a bull turn citing
        # one of them; plus FEAT-03 company identity and a rating.
        return {
            "company_of_interest": "NVDA",
            "trade_date": "2026-11-22",
            "company_identity": {"company_name": "NVIDIA", "industry": "Semiconductors",
                                 "business_description": "Designs GPUs. Also sells software."},
            "market_report": f"Market report {self._marker}.",
            "options_report": "Options report first paragraph.\n\nSecond paragraph cites the chain.",
            "investment_debate_state": {
                "bull_history": f"Bull Analyst: Demand is strong [OPT-02] {self._marker}\n",
                "bear_history": "Bear Analyst: Valuations are stretched [OPT-01]\n",
                "report_paragraphs": [
                    {"id": "OPT-01", "report_key": "options_report",
                     "text": "Options report first paragraph."},
                    {"id": "OPT-02", "report_key": "options_report",
                     "text": "Second paragraph cites the chain."},
                ],
                "turn_citations": [],
            },
            "final_trade_decision": f"Rating: {self._rating}\n\nDecision {self._marker}.",
            "final_rating": self._rating,
        }

    def save_reports(self, final_state, ticker, save_path=None, html=True):
        from tradingagents.reporting import write_report_tree

        self.report_calls += 1
        path = write_report_tree(final_state, ticker, save_path, settings=self.run_settings(), html=html)
        base = path.parent
        self.captured = {
            "md": (base / "complete_report.md").read_bytes(),
            "html": (base / "complete_report.html").read_bytes(),
        }
        return path

    def stream_run(self, graph_input, **kwargs):
        yield [], {"market_report": self._state()["market_report"]}
        yield [], self._state()


CONFIG = {"ticker": "NVDA", "analysis_date": "2026-11-22",
          "analysts": ["market", "options"], "asset_type": "stock"}


def _manager(graph):
    return RunManager(graph_factory=lambda *a, **k: graph, results_root=None)


@pytest.mark.unit
def test_success_exposes_metadata_and_artifacts_for_this_run():
    manager = _manager(_Done(marker="RUN1", rating="Overweight"))
    run_id = manager.start(CONFIG)
    manager.wait_until_done(run_id, timeout=5.0)

    result = manager.result(run_id)
    assert result["ticker"] == "NVDA"
    assert result["date"] == "2026-11-22"
    assert result["rating"] == "Overweight"
    assert "RUN1" in result["html"]
    assert "RUN1" in result["markdown"]


@pytest.mark.unit
def test_viewing_and_downloading_after_completion_starts_no_new_run():
    graph = _Done(marker="RUN1")
    manager = _manager(graph)
    run_id = manager.start(CONFIG)
    manager.wait_until_done(run_id, timeout=5.0)
    calls_after_run = graph.report_calls

    # Reading the preview and the download repeatedly must not re-run anything.
    before = manager.run_count()
    for _ in range(3):
        manager.result(run_id)["html"]
        manager.result(run_id)["markdown"]
    assert manager.run_count() == before
    assert graph.report_calls == calls_after_run


@pytest.mark.unit
def test_two_runs_same_ticker_and_date_keep_separate_artifacts():
    """The factory returns two graphs; each run's artifacts carry only its marker."""
    graphs = [_Done(marker="RUN1"), _Done(marker="RUN2")]
    manager = RunManager(graph_factory=lambda *a, **k: graphs.pop(0), results_root=None)

    first = manager.start(CONFIG)
    manager.wait_until_done(first, timeout=5.0)
    second = manager.start(CONFIG)
    manager.wait_until_done(second, timeout=5.0)

    assert first != second
    assert "RUN1" in manager.result(first)["html"]
    assert "RUN1" not in manager.result(second)["html"]
    assert "RUN2" in manager.result(second)["html"]
    assert "RUN2" not in manager.result(first)["markdown"]


@pytest.mark.unit
def test_preview_adds_citation_anchors_without_altering_saved_files(tmp_path):
    """FEAT-05 anchors are display-only; the bytes the export wrote stay intact."""
    graph = _Done(marker="RUN1", results_root=tmp_path)
    manager = RunManager(graph_factory=lambda *a, **k: graph, results_root=tmp_path)
    run_id = manager.start(CONFIG)
    manager.wait_until_done(run_id, timeout=5.0)

    result = manager.result(run_id)
    # The preview carries an anchor for the cited paragraph.
    assert 'id="para-OPT-02"' in result["html"] or "#para-OPT-02" in result["html"]

    # Exactly one export happened; the on-disk files match the bytes it wrote.
    assert graph.report_calls == 1
    md_path = result["files"]["markdown"]
    html_path = result["files"]["html"]
    assert md_path.read_bytes() == graph.captured["md"]
    assert html_path.read_bytes() == graph.captured["html"]
    # The Markdown download is the very bytes the export produced.
    assert result["markdown"].encode("utf-8") == graph.captured["md"]


@pytest.mark.unit
def test_the_markdown_download_keeps_company_background_and_numbered_paragraphs():
    """FEAT-03 background and FEAT-05 source numbers survive into the download."""
    manager = _manager(_Done(marker="RUN1"))
    run_id = manager.start(CONFIG)
    manager.wait_until_done(run_id, timeout=5.0)

    md = manager.result(run_id)["markdown"]
    assert "Company Background" in md
    assert "NVIDIA" in md
    assert "[OPT-02]" in md  # a numbered source paragraph
