# Architecture blueprint

## Existing application

The CLI in `src/cli/` collects run settings and invokes the graph. `src/tradingagents/graph/` coordinates the four analysts, research debate, trader, risk discussion and portfolio manager. Data tools route through `dataflows/`; model clients live in `llm_clients/`. The graph produces a decision and reports. The memory package records prior decisions and reflections.

## Team design pending

After requirement review, record scope, architectural drivers, external and authority boundaries, integration contracts, workflow changes, permissions, verification, observability and change policy here. Identify the deterministic component that constrains each safety-relevant AI output and link its invariant and negative test.

## FEAT-01 — Options Analyst (specified)

For stock runs, add a fifth parallel analyst to the default selection. Explicit selections take precedence. The proposed selection key is `options` and the proposed state field is `options_report`. The report describes what stock options imply about risk using eligible option-chain evidence. The Market Analyst owns the underlying stock's price and volume analysis.

| Boundary | Producer and consumer contract |
| --- | --- |
| Data access | The data layer receives the stock and analysis cutoff and filters records before model invocation. The model interprets eligible records. The application controls eligibility and the unavailable status. |
| First-stage state | The analyst publishes one options report or an explicit unavailable notice. A deselected analyst issues no lookup or report. Older explicit selections and saved outputs without this field remain readable. |
| Raw evidence | Both researchers and all three risk debaters receive the report, including its unavailable status. |
| Derived evidence | Research Manager reads the debate. Trader reads the investment plan and retains the separate technical market report for price levels. Portfolio Manager reads the risk debate, research plan and trade proposal. A rating change is not required. |
| Presentation and storage | CLI progress and report panels, graph state and saved run logs expose the selected analyst's result. The shared report writer emits a separate Markdown file and a section in the combined Markdown and requested HTML output. |

The scope decision is recorded in [ADR 001](docs/architecture/adr/001-architecture-choice.md). The [trace matrix](docs/architecture/trace-matrix.md) links each contract to its planned verification.

## FEAT-02 — Research debate early stop

The bull and bear researchers already alternate turns. Extend the routing decision in
`src/tradingagents/graph/conditional_logic.py` at the end of a bull–bear pair. The research
debate history is the reference for identifying evidence already cited and opposing arguments
already answered. A paraphrase of the same fact or rebuttal adds no progress.

| Decision point | Next step |
| --- | --- |
| Only the bull has spoken in this round | Give the bear its turn. |
| Both have spoken and the round limit is reached | Hand the history to the Research Manager under the existing limit. |
| Opening round complete and below the limit | Start round two. |
| Later round complete and below the limit | Continue if either side cited a new fact or first addressed an unanswered opposing point. Otherwise record “No new evidence or first response in this round” with the debate and hand the full history to the Research Manager. |

The rule operates on the research debate regardless of which analysts supplied reports. The separate risk debate uses its existing routing.

## FEAT-03 — Company background in the consolidated report

The shared CLI and Python export path prepares one factual introduction from the run's eligible company profile. Both renderers place it between the report header and the analyst reports. Reuse the ticker in the title. The introduction is independent of the Fundamentals Analyst and requires no additional agent or model call.

A run retains its cleaned profile once at initialization: `create_run_state` resolves the instrument identity a single time and keeps only `company_name`, `industry` and `business_description` in the optional state field `company_identity` (declared `NotRequired`, so a run without it stays loadable). A custom `resolve_instrument_context` override still supplies the run's context string; the profile is retained from that same single resolution, and a failed resolution is not retried, so no extra vendor request is made. That field flows through the graph and is persisted in the run log. The exporter reads only stored run data — no lookup, cache access, prompt-text parsing or model call — prepares the background once in `write_report_tree`, and shares the same raw source text between Markdown and the requested HTML. Each renderer escapes for its own format: Markdown escapes Markdown-significant characters so the source text shows literally, and HTML escapes for HTML, so both formats show the same visible text. An independent `Company Background` section (English labels `Name`, `Industry`, `Business`) sits after the header and before the numbered analyst sections; the HTML contents list names it first. The business description keeps one or two complete source sentences split at sentence boundaries, with no character cap.

For historical runs, follow the identity rule in `src/tradingagents/agents/context.py`. A current name may identify the company if explicitly labelled as current. Present industry and business details as historical facts only when supported for the analysis date. Omit missing fields and show an unavailable notice if the profile supplies none.

## FEAT-04 — Per-run token usage warning

The CLI and web entry points share the same per-analysis statistics handler design. Reuse its input and output counters and read the warning threshold from the run configuration. A call with no reported usage contributes nothing to the measured total. Check the total and mark the first crossing under the handler's existing lock so simultaneous completions produce a single warning. Send the crossing total and configured threshold to the active terminal or browser activity view. The graph continues normally.

The run-level warning threshold is independent of `TRADINGAGENTS_MAX_TOKENS`, which controls output length per model call.

## FEAT-05 — Paragraph citations in the research debate

At the handoff from analysts to researchers, assign a stable report prefix and a sequence starting at 01 within each supplied report. For example, `[MKT-01]` identifies the first market paragraph and `[FUN-02]` the second fundamentals paragraph. Treat blank lines as body paragraph boundaries and skip headings and empty blocks. Preserve the original paragraph text. A selected Options Analyst report uses its own sequence (`OPT`). The company background added at export falls outside the debate inputs.

Give both researchers the same labelled text. Each argument carries the ID or IDs for its evidence. Before recording a turn, check each ID against this run's paragraphs. Display “Invalid citation” beside unknown IDs and “No citation provided” beside an argument with none. Preserve these annotations in the debate history and continue. Both consolidated renderers use the original labels so a reader can search for the cited source.

FEAT-02 evaluates progress separately. A first reply to an unanswered opposing point can advance the debate even when both speakers cite the same paragraph.

## FEAT-06 — Local web interface (specified)

The planned `tradingagents web` entry point serves one local user. Print the local URL and open the default browser after the service is ready. The printed URL also works when automatic opening fails. The existing CLI command continues to open the terminal interface.

| Handoff | Contract |
| --- | --- |
| Form to run | Reuse CLI validation, provider/model choices, analyst defaults and graph configuration. Read credentials on the host. Disable Start during an active run and accept only one start for that run. |
| Run to browser | Consume the existing graph stream that feeds the CLI. Show agent status, messages and tool calls in the activity view. In the content view preserve analyst reports, individual bull/bear turns, the research manager's plan, trader proposal, all three risk opinions and the final decision. Append new content in observed order and suppress duplicate items from cumulative snapshots. |
| Feature interactions | FEAT-01 supplies options selection and report or unavailable notice. FEAT-02 supplies the early-stop reason before the manager takes over. FEAT-04 supplies token totals and its single threshold warning. FEAT-05 supplies paragraph IDs, inline citations and validation notices during the debate. |
| Run to results | Use the existing report writer for this run's HTML preview and Markdown download, including FEAT-03 company background and FEAT-05 source labels. Associate results with the run even when two analyses use the same ticker and date. On failure, retain partial activity, show a concise error and re-enable Start. |
