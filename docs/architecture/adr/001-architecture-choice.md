# ADR 001 — Separate Options Analyst for stock runs

**Implemented decision, 22 November 2026.** The team lead chose a fifth first-stage role with its own report, confirmed default inclusion and accepted continuing with an unavailable notice when eligible data is missing. The implementation and its verification evidence are recorded under FEAT-01 in the trace matrix and review memo.

We traced the baseline from analyst registration to the model inputs and report writer. Two researchers and three risk debaters consume the full report set. The trader consumes a separate technical report for price levels. A separate options node fits the first pattern while preserving the latter contract. [Candidate comparison](../evaluation-table.md).

The extra node adds data access, model cost when invoked, and context in five recipients. Revisit the provider or feasible indicator set if a candidate cannot establish snapshot provenance. A change to default selection or the independent-report requirement goes back to the team lead.

**Implemented context design.** The data layer prefetches the yfinance current chain, verifies stock identity and availability, deduplicates contracts and renders the approved core chain-only indicators before the Options Analyst model call. Current stock runs include the analyst by default; crypto runs exclude it. When no eligible snapshot exists, the node publishes the exact unavailable notice without asking the model to infer an options signal. Downstream nodes receive the resulting independent report.

The implemented baseline has no project-wide prompt-context cap or compaction threshold. Existing per-call model output limits and graph/tool/debate caps remain in force. Approving a cross-agent context budget, compaction algorithm and critical-constraint reinjection policy would reopen this part of the decision.

## Input context design and implementation boundary

Each model call starts from the role and standing constraints, the instrument and analysis cutoff, eligible evidence, selected past context, retained state and prior turns, and the current task. The adapter filters by identity and time before it numbers or deduplicates evidence. A researcher sees the same run-local IDs as the exporter. Stored state retains the original evidence even when a model view is shorter.

The proposed input ceiling per turn is the smaller of 16,384 tokens and the provider context limit less the reserved output allowance. Start compacting at 80% of that ceiling. These are design parameters for review, not measured provider limits. Count the assembled request with its model tokenizer. Retain identity, cutoff, role, missing-data policy, authority limits, current task and evidence IDs first. Remove duplicate records and oldest nonessential turns before shortening retrieved prose. Keep each retained claim linked to its source. Reassemble from immutable constraints after compaction and recount. If the protected fields alone exceed the cap, skip the call and return the stage’s documented fallback. Never truncate an identifier or transfer evidence between instruments.

Current source enforces provenance and graph/tool-loop limits. It does not yet have the common input-token counter or automatic compactor. Crossing the cumulative token-warning threshold therefore remains a separate event. Acceptance for a future implementation requires boundary fixtures below, at and above the trigger, a protected-only overflow, and equality of instrument, cutoff and source IDs before and after compaction.
