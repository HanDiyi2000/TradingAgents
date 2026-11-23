"""FEAT-06: the local HTTP server the page talks to, backed by ``RunManager``.

Standard-library ``ThreadingHTTPServer`` only: one local, single-user service.
It serves the page's static files and a small JSON API:

* ``GET  /api/config``                      the form's options and defaults
* ``POST /api/runs``                        start a run; returns ``{"run_id"}``
* ``GET  /api/runs/<id>/events?since=N``    events after ``N`` and the next cursor
* ``GET  /api/runs/<id>/status``            ``{"state"}`` (and the error)
* ``GET  /api/runs/<id>/report``            this run's HTML report
* ``GET  /api/runs/<id>/report.md``         this run's Markdown download

The analysis itself is never re-run here: reading a report or downloading it
serves bytes ``RunManager`` already produced for that run.
"""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

_STATIC = Path(__file__).resolve().parent.parent / "static"

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
}


def build_graph(config: dict, callbacks=None):
    """Construct the real analysis graph from the form's configuration."""
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    selected = config.get("selected_analysts") or []
    return TradingAgentsGraph(selected, config=config, debug=False, callbacks=callbacks)


class _Handler(BaseHTTPRequestHandler):
    server_version = "TradingAgentsWeb/1.0"

    def log_message(self, *args):  # keep the terminal quiet; the launcher prints the URL
        pass

    # --- dispatch -------------------------------------------------------------

    def do_GET(self):  # noqa: N802 (http.server's name)
        parsed = urlparse(self.path)
        path = parsed.path
        if path in ("/", "/index.html"):
            return self._serve_static("index.html")
        if path in ("/app.js", "/style.css"):
            return self._serve_static(path.lstrip("/"))
        if path == "/api/config":
            return self._json(200, self.server.manager_config())
        if path == "/api/models":
            return self._serve_models(parsed)
        parts = path.strip("/").split("/")
        # /api/runs/<id>/<action>
        if len(parts) == 4 and parts[0] == "api" and parts[1] == "runs":
            run_id, action = parts[2], parts[3]
            return self._dispatch_run_get(run_id, action, parsed)
        return self._json(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/runs":
            return self._start_run()
        return self._json(404, {"error": "not found"})

    def _dispatch_run_get(self, run_id, action, parsed):
        manager = self.server.manager
        try:
            if action == "status":
                snap = manager.snapshot(run_id)
                return self._json(200, {"state": snap["state"], "error": snap["error"]})
            if action == "events":
                since = int(parse_qs(parsed.query).get("since", ["0"])[0] or 0)
                events, nxt = manager.events_since(run_id, since)
                return self._json(200, {"events": events, "next": nxt})
            if action == "report":
                return self._serve_run_report(run_id, html=True)
            if action == "report.md":
                return self._serve_run_report(run_id, html=False)
        except KeyError:
            return self._json(404, {"error": "unknown run"})
        except RuntimeError as exc:
            return self._json(409, {"error": str(exc)})
        return self._json(404, {"error": "not found"})

    # --- actions --------------------------------------------------------------

    def _start_run(self):
        body = self._read_json()
        if body is None:
            return self._json(400, {"error": "invalid JSON body"})
        try:
            run_id = self.server.manager.start(body)
        except Exception as exc:  # a rejected configuration is the user's to fix
            return self._json(400, {"error": f"{type(exc).__name__}: {exc}"})
        return self._json(201, {"run_id": run_id})

    def _serve_models(self, parsed):
        from cli.web.config import models_for

        provider = (parse_qs(parsed.query).get("provider", [""])[0] or "").strip()
        try:
            return self._json(200, models_for(provider))
        except Exception as exc:
            return self._json(200, {"quick": [], "deep": [],
                                    "error": f"Could not load models: {exc}"})

    def _serve_run_report(self, run_id, html):
        manager = self.server.manager
        result = manager.result(run_id)  # raises if not succeeded
        if html:
            return self._bytes(200, result["html"].encode("utf-8"),
                               "text/html; charset=utf-8")
        filename = f"{result['ticker']}_{result['date']}_report.md"
        return self._bytes(200, result["markdown"].encode("utf-8"),
                           "text/markdown; charset=utf-8",
                           extra={"Content-Disposition": f'attachment; filename="{filename}"'})

    # --- helpers --------------------------------------------------------------

    def _read_json(self):
        import json

        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None

    def _serve_static(self, name):
        path = _STATIC / name
        if not path.is_file():
            return self._json(404, {"error": "not found"})
        ctype = _CONTENT_TYPES.get(path.suffix, "application/octet-stream")
        return self._bytes(200, path.read_bytes(), ctype)

    def _json(self, status, payload):
        import json

        return self._bytes(status, json.dumps(payload).encode("utf-8"),
                           "application/json; charset=utf-8")

    def _bytes(self, status, body, content_type, extra=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)


class WebServer(ThreadingHTTPServer):
    """A ``ThreadingHTTPServer`` that carries the run manager and its config factory."""

    daemon_threads = True

    def __init__(self, address, manager, config_factory):
        super().__init__(address, _Handler)
        self.manager = manager
        self._config_factory = config_factory

    def manager_config(self):
        return self._config_factory()


def create_server(host: str, port: int, manager: RunManager, config_factory=None):
    """Bind and return a server; raises ``OSError`` (EADDRINUSE) if the port is taken."""
    if config_factory is None:
        from cli.web.config import form_config

        config_factory = form_config
    return WebServer((host, port), manager, config_factory)


def _make_manager(graph_factory):
    from cli.web.runs import RunManager

    return RunManager(graph_factory=graph_factory)


def start_in_thread(host: str, port: int, graph_factory=None):
    """Bind, serve on a background thread, and return ``(server, thread)``."""
    if graph_factory is None:
        import cli.web as _pkg

        graph_factory = _pkg.build_graph
    manager = _make_manager(graph_factory)
    server = create_server(host, port, manager)
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="tradingagents-web")
    thread.start()
    return server, thread


def stop(server, thread=None, timeout: float = 5.0) -> None:
    """Stop serving and wait for the server thread to end."""
    server.shutdown()
    server.server_close()
    if thread is not None:
        thread.join(timeout)


# Imported here so the type name resolves without a runtime import cycle.
from cli.web.runs import RunManager  # noqa: E402
