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
