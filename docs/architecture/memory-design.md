# Memory and state design

This document describes the state that the current implementation actually
stores or transports. It distinguishes transient graph state, crash-recovery
state, human-readable run artifacts and the long-lived decision memory. It does
not treat provider credentials or model configuration as application memory.

## State inventory

| State | Owner | Write and retrieval policy | Retention | Interruption and version handling | Privacy |
| --- | --- | --- | --- | --- | --- |
| In-flight analysis state (`AgentState`) | `src/tradingagents/agents/state.py` defines the contract; graph nodes own their declared fields; `src/tradingagents/graph/propagation.py` creates the baseline state | Nodes return partial updates through LangGraph. Analyst nodes write distinct report keys; debate and risk nodes update their nested states; later nodes read only the fields named by their prompt contract. | Process lifetime unless checkpointing is enabled. The completed state is also the source for reports and the final run log. | Additive compatibility fields such as `company_identity`, `report_paragraphs` and `turn_citations` are `NotRequired` and read with `.get()`. A new required key or a changed meaning needs migration evidence. | May contain reports, debate text and caller-supplied portfolio context. It must not contain API keys, auth tokens or credential-file contents. |
| Checkpoint state | `src/tradingagents/graph/checkpointer.py`; lifecycle calls in `trading_graph.py` | When `checkpoint_enabled` is true, LangGraph writes node state to a per-ticker SQLite database under `<data_cache_dir>/checkpoints/`. The thread ID is derived from ticker, date and the graph-shape signature. | Disabled by default. A successful run removes its ticker/date rows. Explicit clear-all removes the database plus SQLite WAL/SHM files. An interrupted or failed run remains available for retry. | A compatible signature resumes from the latest committed step. Graph-shape-affecting settings are included in the signature so an incompatible run cannot silently reuse state. Optional state fields preserve old checkpoints where possible. | Checkpoints can contain the full run state and therefore receive the same protection as reports. They are local files; no checkpoint content is sent anywhere except through the normal model/tool calls of a resumed run. |
| Final state log | `TradingAgentsGraph._log_state` in `src/tradingagents/graph/trading_graph.py` | At completion, a selected state projection is written as JSON to `<results_dir>/<ticker>/TradingAgentsStrategy_logs/full_states_log_<date>.json`. It includes reports, debates, citation records, plans, final decision/rating and run settings. | One path per ticker/date; a later write to the same path replaces that file. There is no automatic expiry in this component. | New data is additive. Readers must tolerate older logs without optional fields. This log is evidence/replay data, not a checkpoint and cannot resume execution. | Contains generated analysis and identity data. `portfolio_context`, credentials and auth files are not included in `_log_state`. |
| Report tree | `src/tradingagents/reporting.py`; HTML rendering in `src/tradingagents/report_html.py` | `save_reports`/`write_report_tree` derive per-agent Markdown, consolidated Markdown and optional HTML only from the completed state and run settings. Export performs no model call or market-data lookup. | Persisted under the selected result directory until the user removes it. Web runs use a run-specific directory so equal ticker/date runs do not share artifacts. | Old states without optional FEAT-03/05 fields export through deterministic fallbacks. Export is repeatable from the same final state. | Reports may expose company information, generated arguments and decisions. HTML disables raw HTML and external image loading; credentials must never be rendered. |
| Long-lived trading memory | `src/tradingagents/memory/log.py`; outcome settlement in `settlement.py`; lesson generation in `reflection.py` | A completed run appends one pending decision per ticker/date to the configured Markdown log. Later settlement obtains eligible closes, computes raw/benchmark-relative return and atomically replaces the pending record with outcome and a short reflection. Future runs retrieve recent settled same-ticker decisions and cross-ticker lessons. | Default path: `~/.tradingagents/memory/trading_memory.md`. Pending records are always kept. Resolved-record rotation happens only when `memory_log_max_entries` is configured; the default `None` disables rotation. | File locking prevents duplicate writes and concurrent settlement. Temporary-file replacement protects an outcome update from partial writes. Historical runs use `resolved:YYYY-MM-DD` to exclude lessons that were not yet knowable at their as-of date. Malformed entries are ignored rather than injected. | The log contains decisions, realized outcomes and model-generated reflections. It must not contain credentials or portfolio holdings. Users are responsible for protecting or deleting the local file. |
| Portfolio context | Caller and `src/tradingagents/graph/propagation.py` | The CLI parses the supplied portfolio and renders only the run context required by trader/risk/portfolio-manager prompts. It travels in `AgentState`. | In-memory/checkpoint lifetime only. It is deliberately absent from the final JSON projection and the long-lived trading memory. | A run without a portfolio uses an empty string. A resumed checkpoint can contain the same context as the interrupted run. | Holdings and cash are user-sensitive. Do not add them to logs, reports or long-lived memory without a separately approved requirement and privacy review. |
| Web run/event state | `src/cli/web/runs.py::RunManager` | One process-local `_Run` owns an append-only, monotonically indexed event list, status/error, rating and paths/bytes for that run's artifacts. Cursor reads return only events at or after the requested index. | Kept while the local server process lives. Report files remain in the run-specific results directory after the process ends. | A failed run retains partial events and its reason. A new run gets a new ID. This state is presentation state, not graph recovery state. | The local server binds to loopback by design. Events contain model/tool output and must not include credentials. |
| CLI preferences and provider auth | `src/cli/prefs.py` and provider-specific auth modules | Preferences and auth are read by entry points/clients. They configure a run but are not injected wholesale into `AgentState`, run logs or reports. | Stored under the user's `~/.tradingagents/` directory according to the owning module. | Auth refresh and preference migration belong to those owners, not to graph state. | Secret values must never be printed, committed, copied into transcripts or serialized in run evidence. |

## Write, read and ownership rules

1. **One owner per representation.** The graph state contract is owned by
   `agents/state.py`; checkpoint serialization by `graph/checkpointer.py`; the
   final JSON projection by `TradingAgentsGraph._log_state`; report artifacts by
   `reporting.py`; and durable lessons by `memory/log.py`. A renderer may read a
   record but must not silently redefine it.
2. **Model output is not authoritative state policy.** Models propose reports,
   arguments, plans and reflections. Deterministic code decides data cutoff,
   graph routing caps, citation validity, persistence keys, file paths and
   whether a checkpoint is compatible.
3. **Point-in-time reads.** Tools enforce the analysis cutoff before evidence
   reaches analysts. Memory retrieval for historical runs filters by the date an
   outcome became knowable. Export never fetches current data to fill an old
   state.
4. **Backward compatibility.** New fields are additive and optional unless an
   approved migration says otherwise. Old logs and states must keep routing and
   exporting; absence is handled explicitly rather than reconstructed from
   prompt prose.
5. **Idempotence.** Decision memory prevents duplicate ticker/date entries;
   settlement updates only pending entries; citation annotations render from raw
   argument records; repeated report export does not mutate the final state.
6. **Failure isolation.** Missing market evidence produces an explicit
   unavailable result where the requirement permits it. A failed memory
   settlement stays pending. A failed web run keeps already-published events.

## Context and compaction policy

The implementation currently bounds model output through the optional
`max_tokens` setting and bounds analyst tool loops with `max_tool_rounds`. It
does **not** implement a project-wide prompt token cap or automatic context
compaction. Analyst selection, report size and debate/risk round caps therefore
remain the principal context controls. ADR 001 records exact compaction and
token thresholds as an open design decision; no threshold is claimed here.

Any future compaction must preserve the role, ticker, analysis cutoff,
missing-data rule, report/citation identifiers and the state needed for resume.
It must have a deterministic owner and negative tests showing that evidence is
not moved across tickers, dates or arguments.

## Retention and deletion summary

- Checkpoints are recoverable work and are removed after success or by the
  explicit checkpoint-clear operations.
- Final JSON logs and report trees have no automatic retention policy.
- The trading memory is durable; only resolved entries are eligible for optional
  configured rotation, while pending entries are retained.
- Web event history is process-local, but its generated reports are files with
  the same retention as other report trees.
- Credential material is outside all four stores above and must stay there.

The path-level coding-agent permission allowlist remains unapproved and blank in
`docs/architecture/permission-model.md`. This document describes runtime data
ownership; it does not grant an AI agent permission to read or write these
paths.
