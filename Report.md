# CS5351 process report

## Team and relative contributions

This section records the FEAT-01 contribution of Ruihan Zhou and the FEAT-03 contribution of Haobin Yan. The team must add the remaining members and agree the final relative weights so the team average equals 1.0.

| Name | Student ID | Rotated roles | Contribution | Evidence | Relative weight |
| --- | --- | --- | --- | --- | --- |
| Ruihan Zhou | 60468699 | FEAT-01 implementation and verification; role rotation to be confirmed by the team | Read the FEAT-01 requirements and architecture artifacts; produced the plan; implemented the data adapter, yfinance vendor, Options Analyst node, selection, graph, CLI, delivery and export integration; added offline and live tests; completed the verification and delivery records | `src/tradingagents/dataflows/options.py`, `src/tradingagents/dataflows/vendors/yahoo/options.py`, `src/tradingagents/agents/analysts/options_analyst.py`, `test/offline/test_options_data.py`, `test/offline/test_options_analyst.py`, `test/live/test_options_yfinance_live.py`, `docs/architecture/trace-matrix.md`, `docs/review-memo.md`, `docs/ai-use-log.yaml`, this file | To be agreed by the team; the team average must equal 1.0 |
| Haobin Yan | 60642891 | FEAT-03 requirements clarification, coding-agent supervision and manual acceptance; role rotation to be confirmed by the team | Directed OpenCode through plan revisions, test approval, implementation and correction rounds with assistance from a separate review chat; ran AAPL acceptance without the Fundamentals Analyst; reviewed and accepted the transcript annotations and individual reflection | `test/offline/test_company_background.py`, `transcripts/60642891-Haobin-Yan.md`, `docs/architecture/trace-matrix.md`, `docs/review-memo.md`, `docs/ai-use-log.yaml`; AAPL 2026-11-22 manual run recorded in the transcript | To be agreed by the team; the team average must equal 1.0 |

## Engineering process and improvements

FEAT-01 was developed through an explicit plan-and-approval gate. The first pass was planning only: it traced the requirements to the existing graph, CLI, data layer and report writer, named the editable and frozen paths, identified the interface contracts and raised the unresolved provider, prefetch/tool, indicator, crypto and default-selection questions. The human then approved the plan and selected the six decisions: yfinance current snapshots, prefetching, the core chain-only indicator set, crypto exclusion, fresh CLI preselection of the original four plus options, and the exact unavailable notice.

The implementation followed the approved boundaries. A deterministic adapter in `tradingagents.dataflows.options` owns identity matching, availability filtering, deduplication, metric computation, evidence rendering and the unavailable notice. The yfinance adapter is confined to the data layer. The Options Analyst prefetches the eligible evidence, writes `options_report`, and bypasses the model entirely when no eligible evidence remains. The graph, CLI, state log and shared report writer expose the same field, so the CLI and Python export paths stay consistent.

The process improvement that mattered most was moving eligibility before model input. The original design risk was that a model could see a current chain during a historical run or could infer values not present in the evidence. The adapter, the five-recipient delivery contract and the future-snapshot test made that risk deterministic and inspectable. The offline suite uses fixed chains and a recording model; the live test separately checks the real yfinance chain and the historical refusal.

## Requirement volatility, ambiguity and defect trends

Several requirement ambiguities were resolved rather than left implicit:

- The baseline fresh CLI pre-checked no analyst, while OPT-T1 expects a fresh stock run to include the original four plus options. The approved D5 decision now preselects the five available stock analysts and still honours a saved selection of the original four.
- The PRD left the provider and indicator set open. D1 selected yfinance current snapshots; D3 selected a core set computable from chain fields. The historical-coverage limitation is explicit: historical runs use FR-OPT-05 rather than present-day data.
- The requirement did not say whether crypto runs include options. D4 excludes them, consistent with the "stock analysis" wording and the existing crypto filter.
- The exact unavailable text was not specified. D6 fixed one deterministic English notice for empty chains, provider failure and historical no-snapshot cases.
- AGENTS.md names baseline `4cff72b`, while several requirement source fields name `909c6c4`. The implementation used the supplied working tree as authoritative and recorded the conflict in the plan.

No post-implementation FEAT-01 defects were found in the final offline or live runs. The main residual risk is provider coverage: yfinance cannot establish historical option-chain availability, so the feature deliberately trades historical coverage for the stricter INV-OPT-01 rule. Existing graph tests were updated for the fifth analyst and the new router method; the full offline suite showed no regressions.

## How requirements, architecture, implementation and tests evolved together

The requirements registry defined FR-OPT-01 through FR-OPT-05 and INV-OPT-01. ADR 001 selected a separate fifth analyst rather than extending Market Analyst, because the options evidence needs its own selection, report identity and downstream delivery. The runtime policy catalog supplied the three failure behaviors: no data, later/unverifiable observations, and a deselected analyst.

The implementation followed those artifacts in order: data adapter, provider, analyst node, graph registration, state, downstream delivery, CLI and export. The tests were written against the same boundaries: OPT-T1 for selection and defaults, OPT-T2 for grounded report evidence, OPT-T3 for the five direct consumers, OPT-T4 for display/state/export, OPT-T5 for unavailable data, and OPT-T6 for identity and cutoff eligibility. A separate violation test injects a future snapshot and proves it never reaches the model.

The evidence loops back into the trace matrix and review memo. Offline verification is deterministic and runs without network. The live yfinance test complements it by checking the actual provider path. This separation makes the claim precise: the offline suite proves behavior, and the live suite proves provider integration.

## Human interventions and their effects

1. The human required a plan only and prohibited edits, tests, implementation and branches. This forced the design, file ownership, interface contracts and test plan to be reviewed before code existed.
2. The human approved the plan. This authorized implementation but not the unresolved design choices.
3. The human selected D1–D6. This fixed the provider, prefetch shape, indicators, crypto scope, fresh CLI default and unavailable text.
4. The human asked for the verification boundary to be explained. This clarified that the offline suite uses fixed chains and a recording model, while the live test is a separate provider check.
5. The human asked for a delivery audit, then authorized completion of the missing records and fixed the English name form to `Ruihan Zhou`. This produced the trace-matrix evidence, review memo, AI-use entry, annotated transcript and this report section.
6. No Git branch or PR could be created because the delivered directory has no `.git` metadata. This remains a repository-level delivery task for the team.

## Individual reflections

### Ruihan Zhou (60468699)

I worked on FEAT-01, the Options Analyst. My main lesson was that adding an analyst is not only a prompt or graph-node change. The feature only became defensible when the evidence boundary was made deterministic: the adapter had to verify the underlying identity, verify that the chain was available by the analysis cutoff, reject unverifiable timestamps, deduplicate contracts, and compute the approved indicators before the model saw anything. I initially thought of the options report as a model-writing task, but the governance documents made it clear that the model must interpret supplied evidence rather than discover or invent it. The unavailable path was a useful design constraint because it forced me to separate "no data" from "no analysis"; the graph still had to finish with a decision.

The provider decision was the hardest trade-off. yfinance was available and keyless, but it only exposes the current chain. I accepted that historical runs must produce the exact unavailable notice rather than pretend a present-day chain was known in the past. This reduced historical coverage but preserved INV-OPT-01. The six decisions — provider, prefetch, indicators, crypto scope, fresh CLI default and notice text — showed how many requirements were hiding inside an apparently small feature. Writing tests for the deselected case, the saved original-four selection, the five recipients, the historical cutoff and the future-snapshot violation made the design concrete.

I also learned to distinguish offline evidence from live evidence. The offline suite proves deterministic behavior with fixed chains and a recording model; the live yfinance test proves that the provider path, timestamping and historical refusal work against the real service. The final regression (1443 passed, 6 skipped, 100 subtests; live 2 passed; ruff clean) gives me confidence in the implementation, while the missing Git/PR record is a delivery limitation I must resolve with the team repository. If I repeated the work, I would record the AI-use log and annotated transcript alongside implementation rather than after the audit, because the process evidence is part of the deliverable.

### Haobin Yan (60642891)

My contribution was FEAT-03: adding a Company Background section to the consolidated stock analysis report. Although the visible change was small, completing it required decisions about data ownership, historical accuracy, compatibility and verification. I used OpenCode for implementation and a separate review chat to help examine its plans, tests and code. My role was to direct this workflow, approve defined stages and perform a local acceptance run.

The planning stage showed me why a coding agent should explain its data flow before editing files. OpenCode initially proposed using cached identity data during export, but the review chat identified that this would not guarantee consistent results when exporting an old state or using a new process. I requested revisions and accepted a design that retained structured company data during initialization. The exporter then used stored run data without another lookup. This connected a requirement about report content to an explicit architectural boundary.

Test review was another important part of the process. The first draft did not adequately cover the actual CLI and Python export entries or historical filtering in HTML. With review assistance, I requested stronger tests before approving implementation. The revised tests exercised generated artifacts, missing-data behavior, fixed dates and profile retention through the graph. Recording separate test-approval hashes made the sequence of approval and implementation traceable.

The most instructive moment came after the initial implementation passed its tests. The separate review chat identified and probed three additional defects: Markdown interpreted literal profile characters differently from HTML, the new state field was declared required despite being described as optional, and initialization bypassed an existing context method. I did not discover these independently. I used the explanations to request regression tests first, then approved corrections. This demonstrated that passing tests supports specific claims but does not automatically establish every compatibility claim.

I also ran AAPL locally with the Fundamentals Analyst excluded. The run generated both report formats, and the saved artifacts and log were checked with review assistance. This supported the full-profile scenario; historical and missing-data cases remained supported by offline tests.

My main lesson is that supervision requires checking evidence against each claim. OpenCode reported 34 feature tests passing and 1,528 offline tests passing, but lint remained unavailable and the reviewer could not reproduce the full suite successfully. Keeping these limitations visible, preserving the raw session and acknowledging AI assistance made the delivery record more accurate. In future work, I would establish a reproducible test environment earlier and review compatibility boundaries before implementation begins.

Contribution evidence: [annotated OpenCode transcript](transcripts/60642891-Haobin-Yan.md), [FEAT-03 tests](test/offline/test_company_background.py), [trace matrix](docs/architecture/trace-matrix.md), [review memo](docs/review-memo.md), and [AI-use log](docs/ai-use-log.yaml). The reflection and six retrospective annotations were drafted with review-chat assistance and accepted by Haobin Yan before insertion. No final relative contribution weight or review verdict is assigned here.
