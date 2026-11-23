"""FEAT-06 web model selection — ChatGPT subscription and provider switching.

Reproduces the defect found during browser acceptance:

* The normal provider catalog is a list of ``(label, model_id)`` tuples, not
  objects with ``.value``/``.label``, so the page's model boxes came up empty.
* The ChatGPT subscription provider needs the CLI's live ``list_models()`` (and
  its sign-in), not an OpenAI API key. When signed out the page must say to run
  ``tradingagents login chatgpt``; when listing fails it must say so; and it must
  keep the CLI's manual model-ID entry.

And the hand-off: switching provider refreshes both model boxes, and a run
submitted for ChatGPT reaches the backend as ``chatgpt`` with the two chosen model
IDs, without ``OPENAI_API_KEY``.

The HTTP cases carry the ``loopback`` marker; model listing is stubbed so no
external call is made.
"""

from __future__ import annotations

import json
import urllib.request

import pytest

import cli.web as web
from cli.web import config as web_config
from tradingagents.llm_clients.model_catalog import get_model_options

OPENAI_QUICK = get_model_options("openai", "quick")


@pytest.mark.unit
def test_openai_models_are_parsed_from_label_id_tuples():
    """The catalog is (label, id) tuples; both boxes must be filled from them."""
    models = web_config.models_for("openai")
    assert models["quick"], models
    assert models["deep"], models
    # Values are the real model IDs, labels are the human names.
    first_label, first_id = OPENAI_QUICK[0]
    assert {"value": first_id, "label": first_label} in models["quick"]
    # The custom entry is preserved so a manual ID is still possible.
    assert any(m["value"] == "custom" for m in models["quick"])


@pytest.mark.unit
def test_chatgpt_models_come_from_the_subscription_not_an_api_key(monkeypatch):
    """ChatGPT lists models via chatgpt_auth.list_models(), needing no OPENAI_API_KEY."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from tradingagents.llm_clients import chatgpt_auth

    listed = [("Plan Model A", "gpt-plan-a"), ("Plan Model B", "gpt-plan-b")]
    monkeypatch.setattr(chatgpt_auth, "list_models", lambda: listed)

    models = web_config.models_for("chatgpt")
    values = [m["value"] for m in models["quick"]]
    assert "gpt-plan-a" in values and "gpt-plan-b" in values
    assert "custom" in values  # manual entry stays available
    assert "needs_login" not in models


@pytest.mark.unit
def test_chatgpt_signed_out_tells_the_user_to_log_in(monkeypatch):
    from tradingagents.llm_clients import chatgpt_auth

    def _signed_out():
        raise chatgpt_auth.ChatGPTAuthError(chatgpt_auth.LOGIN_HINT)

    monkeypatch.setattr(chatgpt_auth, "list_models", _signed_out)
    models = web_config.models_for("chatgpt")
    assert models.get("needs_login") is True
    assert "tradingagents login chatgpt" in models.get("error", "")
    assert any(m["value"] == "custom" for m in models["quick"])


@pytest.mark.unit
def test_chatgpt_failure_keeps_a_clear_message_and_custom_entry(monkeypatch):
    from tradingagents.llm_clients import chatgpt_auth

    def _unreachable():
        raise chatgpt_auth.ChatGPTUnreachable("OpenAI could not be reached")

    monkeypatch.setattr(chatgpt_auth, "list_models", _unreachable)
    models = web_config.models_for("chatgpt")
    assert models.get("error")
    assert "could not be reached" in models["error"]
    assert any(m["value"] == "custom" for m in models["quick"])


# --- HTTP: provider switch + back-end hand-off ------------------------------------

@pytest.fixture
def server(monkeypatch):
    import socket

    from tradingagents.llm_clients import chatgpt_auth

    monkeypatch.setattr(chatgpt_auth, "list_models",
                        lambda: [("Plan Model A", "gpt-plan-a"), ("Plan Model B", "gpt-plan-b")])

    seen = {}

    class _Graph:
        def __init__(self):
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
            yield [], {"market_report": "Market body.", "final_trade_decision": "Rating: Buy\n\nB.",
                       "final_rating": "Buy"}

    def factory(config, callbacks=None):
        seen["config"] = dict(config)
        return _Graph()

    monkeypatch.setattr(web, "build_graph", factory)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    srv, thread = web.start_in_thread(host="127.0.0.1", port=port, graph_factory=factory)
    try:
        yield f"http://127.0.0.1:{port}", seen
    finally:
        web.stop(srv, thread)


def _get_json(url, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST" if body is not None else "GET")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


@pytest.mark.unit
@pytest.mark.loopback
def test_switching_provider_to_chatgpt_refreshes_both_model_boxes(server):
    base, _seen = server
    # The page's own defaults start on the configured provider (openai).
    status, openai = _get_json(f"{base}/api/models?provider=openai")
    assert status == 200
    assert openai["quick"] and openai["deep"]

    status, chatgpt = _get_json(f"{base}/api/models?provider=chatgpt")
    assert status == 200
    values = [m["value"] for m in chatgpt["quick"]]
    assert "gpt-plan-a" in values
    # The OpenAI model IDs are not offered under ChatGPT.
    assert "gpt-6-luna" not in values


@pytest.mark.unit
@pytest.mark.loopback
def test_a_chatgpt_run_reaches_the_backend_as_chatgpt_with_chosen_models(server):
    base, seen = server
    submitted = {
        "ticker": "NVDA",
        "date": "2026-11-22",
        "llm_provider": "chatgpt",
        "quick_think_llm": "gpt-plan-a",
        "deep_think_llm": "gpt-plan-b",
        "analysts": ["market"],
    }
    status, started = _get_json(f"{base}/api/runs", body=submitted)
    assert status in (200, 201), started
    run_id = started["run_id"]

    import time

    deadline = time.time() + 5
    while time.time() < deadline:
        _status, snap = _get_json(f"{base}/api/runs/{run_id}/status")
        if snap["state"] != "running":
            break
        time.sleep(0.02)
    assert seen["config"].get("llm_provider") == "chatgpt"
    assert seen["config"].get("quick_think_llm") == "gpt-plan-a"
    assert seen["config"].get("deep_think_llm") == "gpt-plan-b"
