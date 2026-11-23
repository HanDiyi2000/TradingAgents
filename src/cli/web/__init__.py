"""FEAT-06: the local, single-user web interface for one stock analysis.

Public surface:

* ``RunManager`` — starts and observes analyses (one active at a time).
* ``build_graph`` — builds the real analysis graph from the form's configuration.
* ``create_server`` / ``start_in_thread`` / ``stop`` — the local HTTP service.
* ``run_web`` — the ``tradingagents web`` launcher: bind, print the URL, open the
  browser once, and serve until interrupted.

The page reuses the existing graph, its stream interpretation (``cli.stream``)
and report writer; nothing here re-implements analysis.
"""

from __future__ import annotations

import webbrowser

from cli.web.runs import FAILED, RUNNING, SUCCEEDED, RunManager
from cli.web.server import build_graph, create_server, start_in_thread, stop

__all__ = [
    "FAILED",
    "RUNNING",
    "SUCCEEDED",
    "RunManager",
    "build_graph",
    "create_server",
    "start_in_thread",
    "stop",
    "run_web",
    "webbrowser",
]

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def run_web(port: int = DEFAULT_PORT, open_browser: bool = True, host: str = DEFAULT_HOST,
            graph_factory=None, echo=print) -> int:
    """Start the service, print its URL, open the browser once, and serve.

    Returns 0 when the service stops normally, 1 when the port is already taken
    (printing an actionable command instead of a traceback).
    """
    from cli.web.server import _make_manager

    if graph_factory is None:
        graph_factory = build_graph
    manager = _make_manager(graph_factory)
    try:
        server = create_server(host, port, manager)
    except OSError as exc:
        suggestion = port + 1
        echo(f"Port {port} is already in use ({getattr(exc, 'strerror', None) or exc}).")
        echo(f"Try a different port, for example:  tradingagents web --port {suggestion}")
        return 1

    url = f"http://{host}:{port}/"
    # The printed URL is the readiness signal; it is shown before any open so it
    # remains usable when the automatic open fails.
    echo(f"TradingAgents web is ready at {url}")
    echo("Press Ctrl+C to stop.")
    if open_browser:
        try:
            opened = webbrowser.open(url)
        except webbrowser.Error:
            opened = False
        if not opened:
            echo(f"Could not open a browser automatically; open {url} yourself.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
    return 0
