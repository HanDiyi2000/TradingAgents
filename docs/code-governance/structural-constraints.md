# Structural constraints

These constraints extend the TradingAgents baseline. They define module
ownership and dependency direction; they do not create a coding-agent path
allowlist. The latter remains pending in
`docs/architecture/permission-model.md`.

## Baseline preservation

1. Keep one analysis implementation. CLI and web entry points must invoke the
   same `TradingAgentsGraph`, graph stream interpretation and report writer.
2. Extend the existing LangGraph state and topology. Do not create a parallel
   workflow for a feature that can be expressed as a node, deterministic helper
   or renderer input.
3. Keep `src/` canonical. Repository-root package paths that point into `src/`
   do not create a second owner.
4. Preserve public entry points and old saved states unless an approved ADR and
   migration explicitly replace them.
5. A model may advise; deterministic code owns validation, routing caps,
   persistence, cutoff enforcement and filesystem effects.

## Architectural ownership map

| Architectural element | Owning module | Shared interface / output | Authority |
| --- | --- | --- | --- |
| Run state schema | `src/tradingagents/agents/state.py` | `AgentState`, `InvestDebateState`, `RiskDebateState` | Authoritative field names and compatibility status |
| Initial state | `src/tradingagents/graph/propagation.py` | `Propagator.create_initial_state` | Authoritative baseline values; optional fields may be omitted until first produced |
| Graph topology and analyst subgraphs | `src/tradingagents/graph/setup.py` | `GraphSetup.setup_graph`, path maps | Authoritative node/edge structure |
| Analyst selection/specification | `src/tradingagents/graph/analyst_execution.py` | `AnalystExecutionPlan`, `ANALYST_NODE_SPECS` | Authoritative mapping from selection key to node, tools and report key |
| Research/risk routing | `src/tradingagents/graph/conditional_logic.py` | `should_continue_debate`, `should_continue_risk_analysis` | Authoritative cap, order and next-node decision |
| FEAT-02 semantic progress judgement | `src/tradingagents/agents/debate_progress.py` | `ProgressResult`, `evaluate_pair`, fixed early-stop reason | Model judgement is advisory; deterministic classifier maps malformed/uncertain output to `UNKNOWN`; router remains authoritative |
| Instrument and portfolio prompt context | `src/tradingagents/agents/context.py` | cleaned identity/profile/portfolio views | Authoritative cleaning and historical-field policy; profile text itself is external data |
| Options evidence eligibility | `src/tradingagents/dataflows/options.py` | `OptionsEvidence`, unavailable notice and rendered evidence | Authoritative identity, availability, expiry and deduplication filter; Options Analyst interpretation is advisory |
| FEAT-05 citation contract | `src/tradingagents/agents/citations.py` | paragraph map, argument records, validation notices, prompt/reader rendering | Authoritative IDs, segmentation and validity; researchers choose cited IDs but cannot make an unknown ID valid |
| Provider clients | `src/tradingagents/llm_clients/` | provider-neutral invoke/stream/callback behavior | Authoritative transport/auth adaptation; model text remains advisory |
| Checkpoint lifecycle | `src/tradingagents/graph/checkpointer.py` plus lifecycle calls in `trading_graph.py` | per-ticker SQLite, signature-based thread ID, clear operations | Authoritative recovery storage |
| Long-lived decision memory | `src/tradingagents/memory/log.py` | pending/resolved Markdown entries and past-context retrieval | Authoritative storage/deduplication; reflection prose is advisory |
| Outcome settlement | `src/tradingagents/memory/settlement.py` | returns, benchmark selection, resolution date | Authoritative calculation from vendor closes; failures leave entries pending |
| Report tree | `src/tradingagents/reporting.py` | `write_report_tree` and section layout | Authoritative artifact contents and placement |
| HTML conversion | `src/tradingagents/report_html.py` | self-contained HTML page | Authoritative escaping/CSP/rendering; must not fetch data or call a model |
| Shared stream semantics | `src/cli/stream.py` | message/chunk interpretation and trace merge | Authoritative meaning shared by CLI and web |
| Per-run token accounting | `src/cli/stats_handler.py` | usage totals and one crossing event | Provider usage is input; locked accumulation and first-crossing behavior are authoritative |
| Web run lifecycle | `src/cli/web/runs.py` | one-active-run manager, ordered event cursor, run-specific artifacts | Authoritative run/event ownership; no analysis logic is reimplemented here |
| Local HTTP transport | `src/cli/web/server.py` | loopback endpoints | Authoritative request validation and bytes served; reports come from the report owner |
| Web presentation | `src/cli/web/static/` | form, activity/content views and preview | Presentation only; it must not reinterpret graph state or fabricate results |

## Dependency direction

- Entry points (`src/cli/`) may construct and drive `tradingagents`, but core
  `tradingagents` modules must not import CLI or web presentation code.
- `graph/setup.py` composes agents and routers. Agent leaf modules such as
  `citations.py` and `debate_progress.py` must not import `tradingagents.graph`;
  this prevents graph/agent cycles and lets tests exercise deterministic policy
  without building the graph.
- Analyst nodes may call approved dataflow tools. Dataflow adapters must not
  depend on agent prompts or report renderers.
- Report renderers read completed state. They must not perform vendor lookup,
  mutate graph state, invoke a model or resume a run.
- Web code consumes the shared stream and report interfaces. It may add
  display-only anchors to the preview, but it must not alter saved artifacts.
- Memory settlement may call market-data and reflection owners, but graph nodes
  consume only the resulting `past_context` and status note; they do not parse
  the memory file themselves.

## Interface and state rules

1. Document every cross-module structure at its owner and at the consuming
   boundary. A dict with durable meaning must have stable keys and tests.
2. New compatibility fields are `NotRequired`/`.get()` unless every old state,
   checkpoint and log is migrated and verified.
3. Nodes running in parallel write disjoint top-level report keys. A feature may
   not introduce two writers for the same state element without an explicit
   reducer and concurrency tests.
4. Stored raw model text remains raw. Deterministic annotations live in owned
   records or are derived once by the owning renderer; repeated processing must
   not duplicate them.
5. Stable identifiers are scoped to one run and derived from stored source
   evidence, never reconstructed from an export or from model prose.
6. A configuration value that changes graph shape must be included in the
   checkpoint signature. Presentation-only settings must not invalidate a
   checkpoint.
7. File paths derived from tickers or run input use the existing safe-component
   helpers and remain inside their configured root.

## Authority boundaries

| Output | Advisory producer | Deterministic constraint |
| --- | --- | --- |
| Analyst report | Analyst LLM | Tool eligibility/cutoff, selected analyst set, bounded tool loop and report state key |
| Debate progress | Quick-tier structured LLM | Schema/classifier, cap-first router, opening-round rule, `UNKNOWN` fail-open |
| Citation choice | Bull/bear LLM | Run paragraph map, syntax extraction, ID validation and fixed notices |
| Investment/risk/final prose | Researcher/manager/trader/risk LLMs | Fixed graph order, round caps, typed state handoffs and final rating parser |
| Memory reflection | Reflection LLM | Deterministic realized/alpha return inputs, pending-entry match, atomic update and point-in-time retrieval |
| Token warning | Provider usage metadata | Per-run locked accumulator and exactly one first-crossing event |

No LLM output may directly choose a filesystem path, change a graph edge,
declare its own citation valid, override a data cutoff or mark a checkpoint
compatible.

## Change and verification gates

- Map a change to a requirement, owner and acceptance case before editing.
- A graph-shape, public-interface, persistence or authority-boundary change
  requires architecture review; a safety-critical revision requires an ADR and
  explicit human approval.
- Tests must include the normal case, a violation/negative case and a legacy or
  resume case when state is affected. Use scripted/offline models for
  deterministic contracts; clearly separate live-model quality evidence.
- Run targeted tests, prior offline regression, structural/lint checks and the
  requirements-schema gate named in
  `docs/code-governance/verification-constraints.md`. Record actual failures and
  skips; do not convert them into passes by description.
- Do not weaken an approved test or edit human-owned requirements/rules to make
  an implementation pass. Return the conflict for human decision.
- New modules and non-obvious enforcement functions should name the requirement,
  ADR or invariant they implement in their module/function documentation. The
  current invariant register contains `INV-OPT-01`; do not claim unapproved
  FEAT-05 or permission invariants.
