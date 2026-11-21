# Architecture blueprint

## Existing application

The CLI in `src/cli/` collects run settings and invokes the graph. `src/tradingagents/graph/` coordinates the four analysts, research debate, trader, risk discussion and portfolio manager. Data tools route through `dataflows/`; model clients live in `llm_clients/`. The graph produces a decision and reports. The memory package records prior decisions and reflections.

## Team design pending

After requirement review, record scope, architectural drivers, external and authority boundaries, integration contracts, workflow changes, permissions, verification, observability and change policy here. Identify the deterministic component that constrains each safety-relevant AI output and link its invariant and negative test.
