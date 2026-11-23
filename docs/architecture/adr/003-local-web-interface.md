# ADR 003 — Local web interface over the existing analysis

**Implemented 23 November 2026.** FEAT-06 adds a local, single-user web page that
drives one stock analysis from configuration through live output to a downloadable
report. It reuses the existing graph, event interpretation and report writer; it
does not add a second analysis path.

## Decision

- **One event interpretation, two views.** The per-step reading of
  `graph.stream_run()` — messages, tool calls, analyst statuses, the research and
  risk debates, the trader plan — moved unchanged from `run_analysis` into
  `cli/stream.py` (`interpret_messages`, `interpret_chunk`, `merge_trace`). The
  CLI keeps painting the Rich live layout; the web folds the same events into an
  ordered log. Both call the same functions, so an event means the same thing in
  each place.
- **Transport.** Standard-library `ThreadingHTTPServer` with native HTML/CSS/JS
  and cursor polling. No new third-party dependency. The page fetches
  `GET /api/config`, starts a run with `POST /api/runs`, and follows
  `GET /api/runs/<id>/events?since=<cursor>`, `/status`, `/report`, `/report.md`.
- **One active run.** `RunManager` holds at most one running analysis; a start
  while running returns the same id, so a double-submit starts once.
- **Reports belong to the run.** Each run writes to its own directory
  (`results/web/<ticker>_<run_id>`), so two runs on the same ticker and date keep
  separate artifacts. Preview and download serve bytes `save_reports` already
  wrote; reading them never re-runs the analysis.
- **FEAT-05 anchors are display-only.** The preview adds `id="para-XXX-NN"` to
  numbered source paragraphs and links valid citations to them. The saved
  Markdown and HTML files are never modified.
- **FEAT-04 warning once per run.** A fresh `StatsCallbackHandler` per run
  forwards its single crossing to the run's event stream; the page shows one
  warning and the analysis continues.

## Launcher

`tradingagents web [--port N] [--no-browser]` binds `127.0.0.1:8000` by default,
prints the URL, opens the browser once when ready, and serves until interrupted.
A taken port prints an actionable command (e.g. `tradingagents web --port 8001`)
instead of a traceback. The bare `tradingagents` command and the `backtest`,
`login` and `logout` subcommands are unchanged.

## Consequences

- The one shared interpretation makes the web view and the terminal agree by
  construction; a change to what counts as an event is made once.
- The web path consumes the same report writer, so FEAT-03 company background and
  FEAT-05 numbering appear in both the preview and the download for free.
- The HTTP layer is deliberately minimal (single user, no accounts, no database).
  Multi-user concerns are out of scope for the course demonstration.
