# ADR 001 — Separate Options Analyst for stock runs

**Implemented decision, 22 November 2026.** The team lead chose a fifth first-stage role with its own report, confirmed default inclusion and accepted continuing with an unavailable notice when eligible data is missing. The implementation and its verification evidence are recorded under FEAT-01 in the trace matrix and review memo.

We traced the baseline from analyst registration to the model inputs and report writer. Two researchers and three risk debaters consume the full report set. The trader consumes a separate technical report for price levels. A separate options node fits the first pattern while preserving the latter contract. [Candidate comparison](../evaluation-table.md).

The extra node adds data access, model cost when invoked, and context in five recipients. Revisit the provider or feasible indicator set if a candidate cannot establish snapshot provenance. A change to default selection or the independent-report requirement goes back to the team lead.

**Implemented context design.** The data layer prefetches the yfinance current chain, verifies stock identity and availability, deduplicates contracts and renders the approved core chain-only indicators before the Options Analyst model call. Current stock runs include the analyst by default; crypto runs exclude it. When no eligible snapshot exists, the node publishes the exact unavailable notice without asking the model to infer an options signal. Downstream nodes receive the resulting independent report.

The project still has no approved project-wide prompt-context cap or compaction threshold. Existing per-call model output limits and graph/tool/debate caps remain in force. Approving a cross-agent context budget, compaction algorithm and critical-constraint reinjection policy would reopen this part of the decision.
