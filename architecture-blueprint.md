# Architecture blueprint

## 1. Scope and status

TradingAgents-CS5351 is a local, single-user multi-agent stock-analysis system.
It accepts a ticker, analysis date, analyst selection, model/provider settings
and optional portfolio context; gathers cutoff-eligible evidence; produces
specialist reports; runs research and risk debates; emits a final rating and
decision; and writes Markdown/HTML artifacts. The terminal and local web page
are two views over the same analysis graph.

FEAT-01 through FEAT-06 are present in the current implementation. This
blueprint describes the implemented architecture, while the requirements,
ADRs, trace matrix and verification records retain the approval/evidence
history. It does not claim that live-model semantic quality is established by
offline tests.

## 2. Architectural drivers

1. **Point-in-time evidence.** A historical analysis must not see observations
   or learned outcomes that were unavailable at its analysis date.
2. **One workflow.** CLI and web must not diverge into separate analysis or
   report implementations.
3. **Supervised AI authority.** Models generate interpretations and prose;
   deterministic code owns eligibility, routing bounds, validation,
   persistence, paths and failure policy.
4. **Traceable output.** Saved artifacts retain the run identity, analyst
   evidence and debate-to-source citation records needed for review.
5. **Resume and compatibility.** Optional checkpointing recovers interrupted
   compatible runs; additive fields do not make old states/logs unreadable.
6. **Bounded execution.** Analyst tool loops and both debates have configured
   caps. Token usage is measured and warned once without stopping the run.
7. **Local security boundary.** Credentials stay with provider clients; the web
   server is loopback/single-user; reports use deterministic escaping and CSP.

## 3. System and external boundaries

| Boundary | Inside the system | Outside / input |
| --- | --- | --- |
| User interface | CLI command, Rich live display, local web server and static page | User choices, optional portfolio file, browser |
| Model boundary | Provider-neutral clients, structured-output helper, callbacks | OpenAI-compatible and other configured providers; model outputs are untrusted/advisory inputs |
| Market-data boundary | Dataflow router, vendor adapters, cutoff/identity filtering | Yahoo/SEC/FRED/other configured sources; availability and completeness are not assumed |
| Execution boundary | LangGraph topology, state, deterministic routers and checkpoint lifecycle | OS process and local filesystem |
| Artifact boundary | JSON run log, Markdown/HTML report tree, decision memory | User-managed storage/retention |

Provider credentials are read from environment/provider auth storage by the
owning client. They are not state fields, run-log fields, report content or
transcript evidence.

## 4. Components and ownership

| Layer | Responsibility | Principal owners |
| --- | --- | --- |
| Entry and presentation | Collect settings, display shared events, launch one local browser run | `src/cli/main.py`, `run.py`, `display.py`, `stream.py`, `web/` |
| Graph orchestration | Construct the graph, parallel analyst plan, route debates, create/resume state | `src/tradingagents/graph/` |
| Agents | Analyst reports, bull/bear research, research plan, trader proposal, risk opinions, final decision | `src/tradingagents/agents/` |
| Deterministic AI constraints | Debate-progress classification, citation numbering/validation, structured-output guards | `agents/debate_progress.py`, `agents/citations.py`, `agents/structured.py` |
| Evidence access | Route configured vendors, normalize symbols, enforce option eligibility/cutoff | `src/tradingagents/dataflows/` |
| Model transport | Provider/client selection, authentication and callbacks | `src/tradingagents/llm_clients/` |
| Memory | Append decisions, settle outcomes, generate/retrieve lessons | `src/tradingagents/memory/` |
| Artifacts | Per-agent/consolidated Markdown, self-contained HTML, final JSON projection | `reporting.py`, `report_html.py`, `TradingAgentsGraph._log_state` |

Detailed module ownership and dependency constraints are in
[structural-constraints.md](../code-governance/structural-constraints.md).

## 5. End-to-end workflow

1. The entry point validates settings and constructs one `TradingAgentsGraph`.
   Run initialization resolves instrument context/profile once, loads optional
   portfolio context and creates the baseline state.
2. The selected analyst subgraphs run in parallel. The default stock selection
   contains Market, Sentiment, News, Fundamentals and Options. The memory step
   runs alongside them and supplies point-in-time past lessons for the Portfolio
   Manager.
3. Each analyst publishes only its report key. Tool-enabled analysts have a
   bounded tool loop; the Options Analyst receives a deterministic prefiltered
   chain or the exact unavailable notice.
4. The Bull and Bear Researchers receive the same numbered analyst paragraphs.
   Each turn is segmented and its written IDs are validated before the recorded
   debate history moves forward.
5. One round is one bull and one bear turn. The configured cap wins. The opening
   round cannot stop early. From round two, the bear node requests one structured
   progress judgement after both sides speak; the deterministic classifier maps
   malformed/uncertain output to `UNKNOWN`, which continues.
6. The Research Manager receives the full recorded history and produces an
   investment plan. The Trader turns it into a transaction proposal.
7. Aggressive, Conservative and Neutral risk debaters alternate under their
   configured cap. The Portfolio Manager receives the plans, risk history,
   optional portfolio context and memory lessons, and produces the final
   decision/rating.
8. A successful run records the decision in long-lived memory, clears its
   checkpoint, writes the final JSON projection and can export the shared report
   tree. The web path stores artifacts in a run-specific directory.

## 6. Authority model

| Decision | Advisory input | Authoritative component and fallback |
| --- | --- | --- |
| Which evidence is eligible | Vendor records | Dataflow adapters enforce ticker/date/contract rules; missing eligible options become the fixed unavailable notice |
| Analyst/research/risk interpretation | LLM prose | Graph fixes recipients, order, state keys and round/tool caps |
| Whether a debate pair progressed | Structured quick-tier judgement | `debate_progress.classify_judgement`; inconsistent, malformed or low-confidence negative results become `UNKNOWN`; cap-first router decides the edge |
| Which paragraph supports an argument | IDs written by researcher | `agents/citations.py` validates against this run's stored paragraph map; unknown and absent IDs receive deterministic notices |
| Token usage warning | Provider-reported usage | Run-local locked `StatsCallbackHandler` totals usage and emits only the first strict threshold crossing |
| What is persisted or served | Completed state and artifacts | State/log/report/run managers select fields and paths; model output cannot select a path or mark itself valid |

## 7. State, memory and recovery

`AgentState` is the live contract. Optional compatibility fields are declared
`NotRequired` and consumed with `.get()`. Checkpointing is disabled by default;
when enabled it stores per-ticker SQLite state under the data-cache root and
uses ticker/date plus a graph signature to prevent incompatible resume. Success
clears the relevant checkpoint.

The final JSON log is an audit projection, not recovery state. The report tree
is a deterministic view of completed state. The append-only decision memory
survives sessions and later settles outcomes/reflections; historical retrieval
filters lessons by the date they became knowable. Full retention, deletion and
privacy rules are in [memory-design.md](memory-design.md).

## 8. Feature contracts

### FEAT-01 — Options Analyst (`FR-OPT-*`, `INV-OPT-01`)

- Stock runs include the `options` analyst by default; explicit selections take
  precedence. Crypto runs exclude options.
- `dataflows/options.py` owns identity, availability, expiry and deduplication.
  It prefetches the chain before model invocation and renders a core indicator
  set. The model is not given an unrestricted option-chain tool.
- The node publishes `options_report` or the exact unavailable notice. Both
  researchers and all three risk debaters receive it; CLI, log and report
  export retain it. Old states without the field remain readable.

The scope choice is recorded in [ADR 001](docs/architecture/adr/001-architecture-choice.md).

### FEAT-02 — Research-debate early stopping (`FR-DEB-01`)

- Applies only to the bull/bear research debate; the risk debate is unchanged.
- Never stop the opening round. From round two, assess progress only after both
  speakers have completed the pair. New evidence or a first substantive reply
  continues; confirmed absence of both records the fixed reason and hands the
  full history to the Research Manager.
- The configured round cap is checked first and always wins. Judgement failure
  is `UNKNOWN` and continues; no free-text retry converts uncertainty into a
  stop.

Offline tests establish routing and failure behavior. The trace matrix records
that three live semantic evaluations did not pass; semantic accuracy is not
claimed as accepted.

### FEAT-03 — Company background (`FR-RPT-01`)

- Initialization retains one cleaned optional `company_identity` containing
  name, industry and business description, while respecting a custom
  `resolve_instrument_context` hook and avoiding an export-time lookup.
- `write_report_tree` prepares one raw profile view. Markdown and HTML escape it
  for their own formats so the same literal information appears in both.
- Exactly one Company Background section appears after the header and before
  numbered analyst sections. Historical output may label the current name but
  must not present undated industry/business details as historical facts.

### FEAT-04 — Per-run token warning (`FR-TOK-01`)

- The CLI and web each create a fresh run-local statistics handler. Missing
  provider usage contributes zero. When the measured total becomes strictly
  greater than the configured threshold, the active interface receives exactly
  one warning with the total and threshold; the analysis continues.
- `TRADINGAGENTS_TOKEN_WARNING_THRESHOLD` configures the warning. It is separate
  from `TRADINGAGENTS_MAX_TOKENS`, which limits model output per call.

See [ADR 002](docs/architecture/adr/002-token-warning.md).

### FEAT-05 — Paragraph citations (`FR-CIT-01`)

- `agents/citations.py` numbers stored analyst-report body paragraphs with
  stable per-report prefixes (`MKT`, `SEN`, `NWS`, `FUN`, `OPT`) and sequences
  beginning at `01`. Headings and fenced code retain their place but receive no
  ID; source text is not duplicated or dropped.
- Both researchers see the same labelled sources and are instructed to put
  bracketed IDs beside supported arguments. Validation reads only IDs actually
  written in that argument. Unknown IDs remain visible with `Invalid citation`;
  arguments with none receive `No citation provided`; debate execution
  continues.
- Raw turns and resolved argument records are stored separately so resume and
  re-export do not duplicate notices. Consolidated Markdown/HTML and individual
  research files preserve the source/argument association.
- FEAT-02 progress remains a separate semantic decision; reuse of a valid source
  ID does not by itself determine progress.

### FEAT-06 — Local web interface (`FR-WEB-*`)

- `tradingagents web` serves a single-user page on loopback, prints the URL and
  optionally opens the browser. The terminal command remains available.
- The page reuses CLI validation/model catalogs, `cli.stream` interpretation,
  the graph and report writer. `RunManager` accepts at most one active run,
  publishes ordered cursor-indexed events, retains partial output on failure and
  owns run-specific artifact paths.
- Success displays ticker/date/rating, a preview of that run's HTML and the
  matching Markdown download. Citation anchors are added only to the preview;
  saved files are unchanged.

See [ADR 003](docs/architecture/adr/003-local-web-interface.md).

## 9. Permissions and security

- Runtime data/tool access is constrained by the configured data vendors,
  provider clients and the loopback HTTP boundary.
- HTML rendering disables raw HTML and external image loading and preserves the
  CSP. User/model text is escaped by the responsible renderer.
- Credentials remain in environment variables or provider-specific auth files
  and are excluded from state/log/report schemas.
- Plan, Build, Test author and Verify use the file allowlists in `.opencode/permissions.jsonc` and the matching project configuration. Writes require a human-approved scope and individual confirmation. Human-authored rules remain frozen.

## 10. Verification and observability

- `docs/architecture/trace-matrix.md` maps requirements to cases and records
  actual evidence. `docs/code-governance/verification-constraints.md` defines
  required gates. Offline scripted-model tests prove deterministic contracts;
  live evaluations are reported separately and cannot be promoted to passes.
- Runtime observability consists of ordered CLI/web events, agent/tool/report
  labels, token counters/warning, explicit unavailable/error notices, persisted
  debate progress/citation records, the final JSON state log, report artifacts
  and decision memory.
- Evidence records must state exact commands, failures, skips and environment.
  Requirements, approvals, live semantic quality and human review verdicts may
  not be inferred from a passing unit suite.

## 11. Change policy and open decisions

1. Requirement and architecture changes precede code. Safety-critical authority,
   graph-shape, persistence or public-interface changes require human approval
   and, where appropriate, an ADR.
2. Extend one owning module and its declared interfaces. Update traceability,
   tests and memory/permission documentation when those contracts change.
3. Preserve approved tests; if evidence exposes a contradictory test or design,
   stop and return the conflict for human decision before changing it.
4. Do not commit credentials, claim unrun evidence or rewrite human approvals.

ADR 001 specifies an input-budget design for review. Runtime enforcement still uses model-output and graph/tool-loop limits. The project config defines the coding roles; the team must approve the paths released for each feature.
