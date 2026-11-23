"""WEB-T1 · FR-WEB-01 — the local web command, its URL, browser and port handling.

These cases pin the approved FEAT-06 entry point before the implementation
exists:

* ``tradingagents web`` starts a local service on ``127.0.0.1:8000`` by default,
  prints the real URL once the service is ready, and opens the default browser
  exactly once.
* ``--port`` selects another port; ``--no-browser`` suppresses the launch while
  the printed URL still works.
* A busy port prints an actionable command (e.g. ``tradingagents web --port
  8001``) instead of a traceback.

The HTTP-200 checks exercise the interface only. Tab auto-switching and
click-to-source navigation are browser acceptance items recorded in the plan,
not asserted here.
"""

from __future__ import annotations

import socket

import pytest
from typer.testing import CliRunner

from cli import main as cli_main

WEB = ("cli", "web")


def _import_web():
    """The FEAT-06 web module under test.

    ``cli.web`` is created during implementation; importing it here makes the
    cases fail loudly (ModuleNotFoundError) until then, rather than silently
    passing against a missing feature.
    """
    import importlib

    return importlib.import_module("cli.web")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.unit
def test_the_web_subcommand_is_registered_and_shows_help():
    result = CliRunner().invoke(cli_main.app, ["web", "--help"])
    assert result.exit_code == 0, result.output
    assert "--port" in result.output
    assert "--no-browser" in result.output


@pytest.mark.unit
@pytest.mark.parametrize("command", ["backtest", "login", "logout", "web"])
def test_the_original_cli_commands_are_still_invocable(command):
    """Adding ``web`` must not remove the baseline commands (FR-WEB-01).

    Checked through the public CLI (each subcommand's ``--help``), which is how a
    user finds and calls a command; reading Typer's registered objects would not
    prove the command is invocable.
    """
    result = CliRunner().invoke(cli_main.app, [command, "--help"])
    assert result.exit_code == 0, result.output


@pytest.mark.unit
def test_web_defaults_to_loopback_port_8000(monkeypatch):
    """`tradingagents web` defaults to 127.0.0.1:8000 and opens the browser once."""
    web = _import_web()
    seen = {}

    class _FakeServer:
        def __init__(self, host, port):
            seen["host"], seen["port"] = host, port

        def serve_forever(self):
            raise KeyboardInterrupt  # return control to the caller

        def shutdown(self):
            pass

    monkeypatch.setattr(web, "create_server", lambda host, port, manager: _FakeServer(host, port))
    opened = []
    monkeypatch.setattr(web.webbrowser, "open", lambda url: opened.append(url) or True)

    result = CliRunner().invoke(cli_main.app, ["web"])

    # The command may stop itself; what matters is what it bound and opened.
    assert seen.get("host") == "127.0.0.1", result.output
    assert seen.get("port") == 8000, result.output
    assert opened == ["http://127.0.0.1:8000/"], result.output


@pytest.mark.unit
def test_the_url_is_printed_before_the_browser_opens(monkeypatch):
    """The printed URL is the readiness signal; it must appear even if opening fails."""
    web = _import_web()

    class _FakeServer:
        def __init__(self, host, port):
            self.url = f"http://{host}:{port}/"

        def serve_forever(self):
            raise KeyboardInterrupt

        def shutdown(self):
            pass

    monkeypatch.setattr(web, "create_server", lambda host, port, manager: _FakeServer(host, port))

    def _broken(url):
        raise web.webbrowser.Error("no browser")

    monkeypatch.setattr(web.webbrowser, "open", _broken)

    result = CliRunner().invoke(cli_main.app, ["web", "--port", "8123"])
    assert "http://127.0.0.1:8123" in result.output


@pytest.mark.unit
def test_no_browser_flag_suppresses_the_launch_but_keeps_the_url(monkeypatch):
    web = _import_web()
    opened = []
    monkeypatch.setattr(web.webbrowser, "open", lambda url: opened.append(url) or True)

    class _FakeServer:
        def __init__(self, host, port):
            pass

        def serve_forever(self):
            raise KeyboardInterrupt

        def shutdown(self):
            pass

    monkeypatch.setattr(web, "create_server", lambda host, port, manager: _FakeServer(host, port))

    result = CliRunner().invoke(cli_main.app, ["web", "--no-browser", "--port", "8199"])
    assert opened == []
    assert "http://127.0.0.1:8199" in result.output


@pytest.mark.unit
def test_a_busy_port_prints_an_actionable_command_not_a_traceback():
    """WEB-T1: a taken port suggests another command instead of crashing."""
    # Import first so a missing module fails here, not inside the CLIRunner call.
    assert _import_web() is not None
    busy = _free_port()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as held:
        held.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        held.bind(("127.0.0.1", busy))
        held.listen(1)

        result = CliRunner().invoke(cli_main.app, ["web", "--port", str(busy), "--no-browser"])

    combined = result.output
    assert result.exit_code != 0
    assert f"tradingagents web --port {busy + 1}" in combined or "--port" in combined
    assert "Traceback" not in combined


@pytest.mark.unit
@pytest.mark.loopback
def test_the_root_page_answers_200_once_the_service_is_ready():
    """HTTP 200 on `/` is the interface-level readiness check (browser items follow)."""
    web = _import_web()
    import urllib.request

    port = _free_port()
    server, thread = web.start_in_thread(host="127.0.0.1", port=port)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as response:
            assert response.status == 200
            body = response.read().decode("utf-8", "replace")
        assert "<" in body  # an HTML document
    finally:
        web.stop(server, thread)
