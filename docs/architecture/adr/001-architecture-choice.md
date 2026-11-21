# ADR 001 — Separate Options Analyst for stock runs

**Scope decision, 22 November 2026.** The team lead chose a fifth first-stage role with its own report, confirmed default inclusion and accepted continuing with an unavailable notice when eligible data is missing. Implementation and test approval are pending.

We traced the baseline from analyst registration to the model inputs and report writer. Two researchers and three risk debaters consume the full report set. The trader consumes a separate technical report for price levels. A separate options node fits the first pattern while preserving the latter contract. [Candidate comparison](../evaluation-table.md).

The extra node adds data access, model cost when invoked, and context in five recipients. Revisit the provider or feasible indicator set if a candidate cannot establish snapshot provenance. A change to default selection or the independent-report requirement goes back to the team lead.

**Proposed context design.** On each analyst turn supply its role and standing evidence constraints, the stock and analysis cutoff, eligible tool evidence, relevant prior tool turns or resumed state, and the current task. Filter by stock and availability first, deduplicate contract observations, prioritize relevant evidence, then compact to the model budget. Reinsert the role, cutoff and missing-data rule after compaction. Downstream nodes receive the resulting report. Exact token cap, compaction threshold and provider are open design decisions pending model selection and measurement.
