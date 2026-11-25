# CS5351 process report

## Team and relative contributions

The six feature owners are identified below. Final contribution weights require the team’s agreement.

| Name | Student ID | Rotated roles | Contribution | Relative weight |
| --- | --- | --- | --- | --- |
| Ruihan Zhou | 60468699 | FEAT-01 implementation and verification; | Read the FEAT-01 requirements and architecture artifacts; produced the plan; implemented the data adapter, yfinance vendor, Options Analyst node, selection, graph, CLI, delivery and export integration; added offline and live tests; completed the verification and delivery records | 1.0 |
| Yue Xia | 60472258 | FEAT-02 planning, acceptance-test review, implementation supervision and live evaluation review | Supervised the early-stop decision and handoff, corrected the turn-count fixtures, reviewed three live semantic evaluations and documented the unresolved mismatches. | 1.0 |
| Haobin Yan | 60642891 | FEAT-03 requirements clarification, coding-agent supervision and manual acceptance; | Directed OpenCode through plan revisions, test approval, implementation and correction rounds with assistance from a separate review chat; ran AAPL acceptance without the Fundamentals Analyst; reviewed and accepted the transcript annotations and individual reflection | 1.0 |
| Wanxin Ma | 60013670 | FEAT-05 planning, coding-agent supervision, test approval and live citation evaluation;| Directed OpenCode through plan revisions and explicit test/implementation gates; reviewed supplementary and regression tests before production fixes; verified paragraph numbering, citation validation, resume and exports; requested a six-turn real-model citation-quality evaluation and limited the final correction to the demonstrated duplicate-notice display defect | 1.0 |
| Han Diyi | 60021318 | FEAT-06 planning, coding-agent supervision, browser acceptance and delivery records;| Directed an OpenCode session through a read-only plan approval, an offline-test round (tests first, allowed to fail pending implementation), an implementation round, and two evidence-driven fixes found in browser acceptance (ChatGPT subscription model selection; the long analysis-process page); performed the browser acceptance checks | 1.0 |
| Yiheng YANG | 60006550 | FEAT-04 plan, test and revision approval; local acceptance | Directed the per-run token warning, reviewed the threshold display and requested the narrow-terminal correction before delivery. | 1.0 |

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

### FEAT-05: test evidence revising the citation architecture

FEAT-05 used the same supervised order but required more revision rounds. The
first plan defined a deterministic authority boundary: the model may write
paragraph IDs, while code owns paragraph numbering, per-argument extraction,
validation, notices, state and export. The student required plan approval first,
then a test-only patch, explicit test approval, implementation review and final
verification. The accepted tests covered stable numbering for both researchers,
invalid and absent references, Options compatibility, the FEAT-02 judge input,
legacy states, exports and real checkpoint resume.

Implementation evidence then exposed six behaviors missing from the approved
cases: the prompts did not explicitly tell researchers how to cite; citation
state fields were required rather than optional; labels past 99 did not
round-trip; headings became arguments; fenced code was split; and bull/bear
turn numbers used a shared scale. Supplementary tests were reviewed before the
source was corrected. A later probe found three more segmentation/rendering
defects: a heading could consume a numbered entry and duplicate the last body,
prose immediately above a fence could be dropped, and a debate fence could be
misclassified as its own argument. Regression tests again preceded the source
change. This sequence changed the architecture of the citation leaf from a
blank-line iterator into a fence-aware source/argument parser while preserving
the approved state and graph interfaces.

The final offline acceptance proved deterministic behavior, not citation
meaning. The student therefore requested a separate live evaluation using six
real researcher turns. It found that all 139 written IDs resolved, but the
AI-assisted semantic review marked some valid-ID claims as insufficiently
supported. It also reproduced an obvious display defect: when the model echoed
an italic notice, rendering appended the same notice again. The student limited
the final change to that demonstrated duplication; a focused regression test
was added and the wider semantic-quality result remained explicitly unaccepted.
This distinction between syntactic validity, deterministic traceability and
semantic support is retained in the trace matrix, review memo and debt register.

### FEAT-06: requirements, design and tests changing together

FEAT-06 shows a feature whose design changed because of what the browser actually did, not because of a new requirement. The plan reused the CLI's analysis, event interpretation and report writer, and the first offline round passed: 27 web tests green inside a full offline suite of 1647 passed. Those tests pinned the approved interface and behaviour, but they ran against stubbed graphs and did not exercise the real provider and model choices.

Browser acceptance then exposed a gap the offline tests could not: the page did not support the CLI's ChatGPT subscription sign-in. The student uses a ChatGPT Plus/Pro plan rather than an OpenAI API key, and the page listed no plan models. The agent first wrote `test_web_models.py`, whose six cases failed against the current code; they reproduced two concrete defects — the static catalog's `(label, model_id)` tuples were read as objects, and ChatGPT's live `chatgpt_auth.list_models()` was never called. Only then were `cli/web/config.py`, the `/api/models` endpoint and the page's model refresh fixed, so a signed-in plan lists its models, a signed-out plan points to `tradingagents login chatgpt`, and a run reaches the backend as `chatgpt` with the two chosen IDs and no `OPENAI_API_KEY`.

A second acceptance note — the analysis-process page grew very long — led to an offline event-stream test (`test_web_display.py`) and a display change: fixed configuration and tabs, collapsible long output, one in-flight poll by run_id and cursor, and preserved scroll and expansion. The final offline suite is 1657 passed, 1 skipped, 1 deselected, 100 subtests passed. The point is not only that the number rose; it is that the requirement (use the existing subscription workflow), the design (a live `/api/models` endpoint rather than a static list) and the tests (a failing reproduction first) moved together, with the browser as the trigger.

## Human interventions and their effects

1. The human required a plan only and prohibited edits, tests, implementation and branches. This forced the design, file ownership, interface contracts and test plan to be reviewed before code existed.
2. The human approved the plan. This authorized implementation but not the unresolved design choices.
3. The human selected D1–D6. This fixed the provider, prefetch shape, indicators, crypto scope, fresh CLI default and unavailable text.
4. The human asked for the verification boundary to be explained. This clarified that the offline suite uses fixed chains and a recording model, while the live test is a separate provider check.
5. The human asked for a delivery audit, then authorized completion of the missing records and fixed the English name form to `Ruihan Zhou`. This produced the trace-matrix evidence, review memo, AI-use entry, annotated transcript and this report section.
6. The original FEAT-01 working copy lacked Git metadata. The shared repository later recorded the implementation in `b9138f3`. A corresponding reviewed PR has not been identified in the submitted evidence.

### FEAT-05 human interventions (Wanxin Ma)

1. Required OpenCode to read the governing requirements and architecture and to
   produce only a plan, with unresolved decisions returned for human approval.
2. Approved the corrected plan, then limited the next stage to tests and stopped
   implementation until those tests were explicitly accepted.
3. Rejected contradictory or weak test assumptions, including the resume fail
   point, notice ownership, fenced-code behavior and exact HTML association,
   until probes demonstrated what each case would detect.
4. Approved implementation only after the approved test hashes were recorded,
   then requested supplementary tests when review probes found six uncovered
   behaviors.
5. Requested a small real-model evaluation to separate valid-ID handling from
   the quality of the evidence-to-claim relationship.
6. Restricted the final code change to the reproduced duplicate-notice display
   problem and stopped further modification when no other obvious display fix
   was authorized.

### FEAT-06 human interventions (Han Diyi)

The FEAT-06 development session (OpenCode, `CS5351/DeepSeek-V4-Flash`; recorded in [the annotated transcript](transcripts/60021318-Han-Diyi.md)) had these interventions:

1. Planned only first: the student required a read-only analysis and a Chinese plan before any code, forbidding file changes, dependency installs and Git operations in that round.
2. Approved the plan but scoped the next round to offline tests only, and required a shared CLI/web event interpretation; tests were allowed to fail pending implementation rather than prompting production code to make them pass.
3. Reviewed the tests and required one real-HTTP end-to-end case, name/assertion agreement, a byte-level export comparison against the single export, and CLI command checks through `--help`.
4. Approved implementation after three test fixes, and required the diff and a stop before the post-diff verification gates.
5. Found in browser acceptance that the ChatGPT subscription path did not work, and required an offline reproduction before the fix.
6. Found in browser acceptance that the analysis-process page was too long to review, and requested a small display optimisation.
7. Closed development and requested the FEAT-06 course deliverables as documentation only.

## Individual reflections

### Ruihan Zhou (60468699)

I worked on FEAT-01, the Options Analyst. My main lesson was that adding an analyst is not only a prompt or graph-node change. The feature only became defensible when the evidence boundary was made deterministic: the adapter had to verify the underlying identity, verify that the chain was available by the analysis cutoff, reject unverifiable timestamps, deduplicate contracts, and compute the approved indicators before the model saw anything. I initially thought of the options report as a model-writing task, but the governance documents made it clear that the model must interpret supplied evidence rather than discover or invent it. The unavailable path was a useful design constraint because it forced me to separate "no data" from "no analysis"; the graph still had to finish with a decision. The provider decision was the hardest trade-off. yfinance was available and keyless, but it only exposes the current chain. I accepted that historical runs must produce the exact unavailable notice rather than pretend a present-day chain was known in the past. This reduced historical coverage but preserved INV-OPT-01. The six decisions — provider, prefetch, indicators, crypto scope, fresh CLI default and notice text — showed how many requirements were hiding inside an apparently small feature. Writing tests for the deselected case, the saved original-four selection, the five recipients, the historical cutoff and the future-snapshot violation made the design concrete. I also learned to distinguish offline evidence from live evidence. The offline suite proves deterministic behavior with fixed chains and a recording model; the live yfinance test proves that the provider path, timestamping and historical refusal work against the real service. The final regression (1443 passed, 6 skipped, 100 subtests; live 2 passed; ruff clean) gives me confidence in the implementation, while the missing Git/PR record is a delivery limitation I must resolve with the team repository. If I repeated the work, I would record the AI-use log and annotated transcript alongside implementation rather than after the audit, because the process evidence is part of the deliverable.

### Yue Xia (60472258)

For FEAT-02, I had to decide what evidence justified ending a debate before the configured round limit. The routing rule was straightforward once a completed bull/bear pair had a confirmed result. The harder question was what counted as progress. A researcher might introduce a new fact, or might answer an opposing argument for the first time using facts already on the table. In reviewing SEM-05b, I asked for an example where the first reply was the only reason to continue. If the example also contained new evidence, the test could pass even when the judge missed the reply entirely. During implementation, six scheduling fixtures exposed a different problem. They treated the count received by the bear node as though it already included the bear’s own turn. I approved a correction to the fixtures after tracing when the count changes. Changing the router to satisfy those expectations would have tested the wrong point in the conversation. The live evaluation required a separate decision. A single CityU request returned a valid structured judgement, which showed that the provider and parser could work together. When we replayed the full labelled set, the first run produced five mismatches. I asked for the history and the expected and observed flags for each side. On the second run, SEM-04 still disagreed about whether the bear had answered the bull. I approved a clearer reply but required delayed cost pass-through to remain a possible explanation, because the fixture supplied no evidence that it had actually occurred. The third run still disagreed on SEM-02 and returned no structured judgement for SEM-04. I kept those outcomes in the handoff. The offline tests supported the routing contract, including continuing on an uncertain judgement. The live evidence left the judge’s semantic accuracy open. The clearest lesson from these checks is that a reviewer needs to know exactly which claim each passing test supports.

### Haobin Yan (60642891)

My contribution was FEAT-03: adding a Company Background section to the consolidated stock analysis report. Although the visible change was small, completing it required decisions about data ownership, historical accuracy, compatibility and verification. I used OpenCode for implementation and a separate review chat to help examine its plans, tests and code. My role was to direct this workflow, approve defined stages and perform a local acceptance run. The planning stage showed me why a coding agent should explain its data flow before editing files. OpenCode initially proposed using cached identity data during export, but the review chat identified that this would not guarantee consistent results when exporting an old state or using a new process. I requested revisions and accepted a design that retained structured company data during initialization. The exporter then used stored run data without another lookup. This connected a requirement about report content to an explicit architectural boundary. Test review was another important part of the process. The first draft did not adequately cover the actual CLI and Python export entries or historical filtering in HTML. With review assistance, I requested stronger tests before approving implementation. The revised tests exercised generated artifacts, missing-data behavior, fixed dates and profile retention through the graph. Recording separate test-approval hashes made the sequence of approval and implementation traceable. The most instructive moment came after the initial implementation passed its tests. The separate review chat identified and probed three additional defects: Markdown interpreted literal profile characters differently from HTML, the new state field was declared required despite being described as optional, and initialization bypassed an existing context method. I did not discover these independently. I used the explanations to request regression tests first, then approved corrections. This demonstrated that passing tests supports specific claims but does not automatically establish every compatibility claim. I also ran AAPL locally with the Fundamentals Analyst excluded. The run generated both report formats, and the saved artifacts and log were checked with review assistance. This supported the full-profile scenario; historical and missing-data cases remained supported by offline tests. My main lesson is that supervision requires checking evidence against each claim. OpenCode reported 34 feature tests passing and 1,528 offline tests passing, but lint remained unavailable and the reviewer could not reproduce the full suite successfully. Keeping these limitations visible, preserving the raw session and acknowledging AI assistance made the delivery record more accurate. In future work, I would establish a reproducible test environment earlier and review compatibility boundaries before implementation begins.

Contribution evidence: [annotated OpenCode transcript](transcripts/60642891-Haobin-Yan.md), [FEAT-03 tests](test/offline/test_company_background.py), [trace matrix](docs/architecture/trace-matrix.md), [review memo](docs/review-memo.md), and [AI-use log](docs/ai-use-log.yaml). The reflection and six retrospective annotations were drafted with review-chat assistance and accepted by Haobin Yan before insertion. No final relative contribution weight or review verdict is assigned here.

### Han Diyi (60021318)

I used my usual TradingAgents sign-in as a simple acceptance test for the web interface. In the terminal, I could choose my ChatGPT subscription, pick a model and start an analysis. In the browser, both model boxes were empty and the error asked me for an OpenAI API key. This was a useful result to set beside the first 27 passing web tests. Earlier, I had asked OpenCode to write the tests before the implementation. I could then read what each test expected while the feature was still missing. One test checked that the Options Analyst appeared in a CLI helper. It could have passed even if the browser had left that analyst off the form. I asked for a test that submitted a configuration over HTTP and retrieved a specific event while the analysis was still running. That gave me a concrete reason to trust the result for streaming. The subscription failure showed where that trust ended. Our plan said the web interface would reuse the CLI workflow, but it never followed a signed-in user from provider selection to a usable model. The tests inherited that omission. Next time I would put the two sign-in paths in the acceptance plan and try my own path before reviewing the rest of the interface. I used a different standard for the long process log and the possible polling problem. I had seen how difficult it was to find an earlier report once several agents had printed their output. That observation justified folding long entries while keeping their full text available. I had no comparable browser evidence that events appeared twice. There I wanted a controlled test with a delayed response and a repeated cursor before describing the risk or accepting a fix. Keeping those records separate also matters to the next person reading our report: they can tell which problem a user experienced, which condition an offline test exercised, and what still needs a live check.

Contribution evidence: [annotated OpenCode transcript](transcripts/60021318-Han-Diyi.md), [FEAT-06 tests](test/offline/test_web_http.py), [local web interface ADR](docs/architecture/adr/003-local-web-interface.md), [trace matrix FEAT-06 record](docs/architecture/trace-matrix.md), [review memo](docs/review-memo.md), [bug diary](docs/bug-diary.md) and [AI-use log](docs/ai-use-log.yaml). The English wording was prepared with Codex assistance from the recorded development session and browser feedback.

### Wanxin Ma (60013670)

Working with OpenCode on TradingAgents changed how I think about supervising an AI coding agent. My main contribution in the recorded session was guiding FEAT-05, which links arguments in the bull and bear debate to numbered paragraphs in analyst reports. At first, I thought the requirement was mainly about displaying citation labels. The planning discussion showed me that it also required decisions about what counts as an argument, who assigns paragraph IDs, how invalid citations are handled, and whether the same information survives a resumed run. The most difficult part was resolving ambiguity before implementation. OpenCode’s first plan treated an entire researcher turn as one argument and allowed a citation map to supply references that the researcher had not actually written. I rejected that plan and required revisions: citations had to come from the current argument, while deterministic code would validate them and add notices. This was a useful example of human oversight catching a plausible design that did not satisfy the requirement. We then separated plan approval, test approval, implementation review, and verification. Those boundaries made it easier to see what had been proposed, what had been tested, and what was still awaiting review. The defect trend was also instructive. Passing the initial feature tests did not mean the implementation was complete. During review, I identified uncovered problems, including missing citation instructions in researcher prompts and inconsistent turn numbering. Later, a live evaluation exposed duplicated notices in rendered debate text. The team added targeted regression tests and kept the earlier evaluation artifacts as historical evidence, with a note explaining that they predated the fix. The process taught me to preserve failed evidence instead of rewriting the record after a correction. Keeping artifacts aligned required attention throughout these changes. The requirement, architecture blueprint, trace matrix, tests, review findings, and AI-use log each served a different purpose; changing code alone would not explain why its behavior was acceptable. I also learned to question verification claims. An earlier test run used an environment with a potentially stale installed package, so its result could not safely stand as evidence for the repository. OpenCode had also installed packages during planning without authorization, which needed to be recorded honestly. Next time, I would define argument boundaries and test fixtures earlier, check the test environment before relying on suite counts, and review live output alongside deterministic test results. I would still require human review of citation meaning: passing structural checks does not establish that a cited paragraph supports an argument.

### Yiheng YANG (60006550)
Working on FEAT-04 taught me how much care is needed to turn a seemingly simple feature into a verifiable software requirement. At first, “warn when token usage exceeds the limit” sounded like a small change to the existing token counter. After reviewing the requirements and the TradingAgents code with Codex, I learned that we had to define the threshold precisely: the warning should appear only when cumulative usage is strictly greater than the configured value. We also had to decide how to handle missing usage data, concurrent model calls, repeated analyses in one process, and a notification failure without interrupting the analysis.My role was to direct and review the development process. I approved the implementation plan before tests were written, reviewed the proposed acceptance tests before production code was changed, and approved a later test correction when an assumption about the existing max_tokens configuration proved wrong. This sequence helped me see why tests also require review: an incorrect test can demand a change to working behavior. We kept the CLI acceptance results separate from the browser acceptance tests, because the browser entry point had not yet been implemented.The most important review happened after the initial local acceptance. Before submitting, I asked Codex to check the requirement again and look for conflicts with the features already implemented. That check found a defect the earlier tests missed: in a narrow terminal, the warning showed the token count but cut off the threshold. Since the requirement called for both values, I did not treat the feature as complete. I approved a focused fix and additional regression tests, then reviewed the new results. The final local checks reported 23 FEAT-04 tests passing, 173 targeted tests passing, and 1,551 offline tests passing. These results supported CLI acceptance, while browser acceptance remained pending.The transcript also showed me that delivery is part of the engineering process. The first GitHub submission route failed because the connected integration could not write to the team repository. After authorizing another route, we made three separate commits for tests, implementation, and documentation. I then clarified that I wanted those commits directly on CS5351; the branch was fast-forwarded without an extra merge commit.Next time, I would include narrow-terminal cases in the first test proposal and clarify the intended Git branch workflow earlier. This experience made human review concrete for me: asking for one more requirement check caught a real defect before submission.

## Engineering evidence across the six changes

A reader can reproduce a design decision only when the input, the component with authority, and the test observation can be identified separately. For example, a vendor returning a chain says nothing about whether the chain was available on the analysis date. The adapter can decide eligibility; the analyst can interpret what remains. The same distinction applies to the debate judge, citation renderer and browser. The following records assemble the relevant observations by decision and state where the evidence ends.

### Selecting evidence before inference

The fifth analyst changes two boundaries. Selection controls whether a request is made at all. Eligibility controls which contracts can reach the model after a request succeeds. Testing only the text of a finished report would miss a call made for a deselected analyst and could miss an ineligible record omitted by chance from the prose. The adapter fixtures therefore inspect the admitted observations, while the recording-model fixture checks what was actually sent to inference. The separate routing checks identify the recipients. Together the three observations discriminate between an acquisition defect, a model-input defect and a downstream handoff defect.

A provider’s answer to a request for an old analysis date deserves particular attention. Receiving a current chain is a successful network request and an unusable historical observation. Continuing with a visible unavailable notice preserves the time boundary while allowing the rest of the graph to finish. This is the reason that the live smoke check and deterministic cutoff test support different claims. A provider that later offers historical snapshots would change the adapter’s evidence, while the analyst selection and five-recipient delivery contract could stay the same.

### Defining what counts as progress

The early-stop requirement gives both speakers a chance to respond. A turn counter records how many utterances exist, while a judgement describes the meaning of one completed pair. Using a previous pair’s verdict after a resume, judging the opening statement, or judging after the configured cap has already ended the discussion would produce plausible output on the wrong branch. The scheduling fixtures make the round number part of the oracle. The fixed stop reason also gives downstream consumers an observable event independent of how the manager summarizes the conversation.

The live evaluation exposed a more difficult question. A reused number can be evidence of a new relationship, and similar wording can express a first answer to an earlier objection. A schema-valid provider response can still miss that distinction. The single guarded probe showed the service could return structured output. The later labelled runs tested a different claim and recorded disagreement. A clean result on routing therefore supports the control flow while the semantic acceptance decision remains open. A future prompt comparison should retain the fixture text and expected flags, and publish disagreements by case and speaker.

### Keeping exported company information reproducible

The company profile must describe the same run in both export formats. Fetching it again during export would make the artifact depend on current provider state and the availability of a network connection. Keeping the profile in run state gives the exporters a common input, including when Fundamentals Analyst was deselected. For legacy data there is no guarantee that the field exists. The optional-field contract thus affects static typing, checkpoint loading and rendering of the missing-data notice.

The review found separate failures at each of those boundaries. Text resembling Markdown markup could acquire different visible meaning in the two formats. A required typed key contradicted an older state that legitimately omitted it. An initialization path could bypass an extension’s identity resolver. Each failure justified a different regression test. A human opening a single recent report could confirm placement and readability; that observation alone would say little about old checkpoints or subclass behavior.

### Observing a resource limit without interrupting a run

The token warning is deliberately informational. The model’s output limit, the provider context window and the run’s cumulative usage counter answer different questions. The callback owns the cumulative total across model tiers. It captures the first strict crossing while holding the lock, then delivers the notification outside the lock. That order keeps a failing or delayed recipient from owning the analysis state. A second completion must increase the total without creating another crossing event. In a new run the counter must start independently.

The narrow-terminal defect illustrates the difference between storing the correct numbers and communicating them. A test that checked only the warning object would pass even if the reader could see the total but not the configured threshold. Rendering at the observed widths made the presentation failure reproducible. The fix retained the accounting boundary and extended the display tests. The web view later subscribed to the same event; it did not introduce its own threshold comparison.

### Following a citation through the full system

A citation has at least three independently testable properties. The ID must exist in the run-local paragraph map, it must stay associated with the argument that cited it, and the source paragraph must substantively support the claim. The first two are deterministic. The third requires an examination of meaning. Preserving the raw model turn lets a reviewer inspect what the model actually wrote after a rendering rule has changed. Recomputing the numbering from the exported debate would lose the independent source of truth.

The preview adds a fourth property: clicking a valid reference should land on the original analyst paragraph. A report might contain the same visible string in the source, in a bull argument and in the research decision. Counting valid strings or finding any matching HTML target does not establish correct navigation. The final working-tree regression fixture deliberately includes repeated text. It requires exactly one target and checks where that target lives. The reproduced failure was a preview issue and should be tracked independently from the six-turn semantic sample.

### Reusing the event stream across entry points

A streaming HTTP view must display progress before the graph finishes. A test that starts and completes a graph inside a single call cannot distinguish real incremental publication from replaying a list at the end. The pausable graph fixture gives the verifier a point at which the first event must already be readable. A repeated cursor distinguishes a genuinely new event from an earlier item returned twice. Consecutive runs for one symbol distinguish run ownership from a filename derived only from the ticker and date.

The same evidence explains why opening a report should be cheap. Once the analysis completes, a reviewer is retrieving a specific pair of artifacts. Starting another graph could change the report, charge for more inference and mix two runs in the browser. The tests count backend invocations as well as comparing downloaded bytes. Real browser inspection then tests a different boundary: the selected account type, model listing, user-visible controls and navigation. A model-list failure can prevent a user reaching any graph test at all.

### Requirement-by-requirement acceptance record

The registry and trace matrix remain the maintained sources. The following review pairs each obligation with the measurement that would expose its failure. A threshold here describes the acceptance test; recorded outcomes appear in the evidence sections below.

**FR-OPT-01**  Select Options Analyst by default alongside the four existing analysts for stock analysis. Honor explicit selections, including saved selections that omit options.

The recorded tradeoff is as follows. Default coverage adds a data lookup and may add a model call. Explicit selection controls this cost. The verifier measures selection cases with incorrect active analysts or unexpected options calls. The registered threshold is `0`. Evidence: OPT-T1 in docs/code-governance/verification-constraints.md.

**FR-OPT-02**  When usable options evidence exists, produce a separate report for the selected stock and analysis date. Ground its interpretation in the option chain. Market Analyst retains responsibility for technical analysis of the underlying stock.

The recorded tradeoff is as follows. A separate report preserves evidence provenance and adds a report to the workflow. The verifier measures fixture runs yielding one identifiable options report grounded in the supplied option-chain evidence. The registered threshold is `1`. Evidence: OPT-T2 in docs/code-governance/verification-constraints.md.

**FR-OPT-03**  Deliver the options report to the bull and bear researchers and to each of the three risk debaters. Carry their reasoning forward through the existing research plan, trader proposal and final decision interfaces.

The recorded tradeoff is as follows. Direct delivery gives both debates access to the evidence at the cost of extra context. The verifier measures distinct direct recipients whose model input contains the options report marker. The registered threshold is `5`. Evidence: OPT-T3 in docs/code-governance/verification-constraints.md.

**FR-OPT-04**  Show the selected analyst and its report in the CLI. Include the report in the run state and saved log, the individual Markdown report and the consolidated reports produced by the existing CLI and Python export paths.

The recorded tradeoff is as follows. One additional section increases report size and makes the evidence inspectable. The verifier measures required display, state, log or export locations missing the fixture report. The registered threshold is `0`. Evidence: OPT-T4 in docs/code-governance/verification-constraints.md.

**FR-OPT-05**  When selected and no usable options data exists for the analysis date, publish an explicit data-unavailable report, deliver and save it through the usual paths, and continue the stock analysis to a final decision.

The recorded tradeoff is as follows. A run can finish with less evidence. The status makes that limitation visible. The verifier measures unavailable-data cases missing the notice, the delivery, the saved report or the final decision. The registered threshold is `0`. Evidence: OPT-T5 in docs/code-governance/verification-constraints.md.

**INV-OPT-01**  Only admit options evidence attributable to the requested stock and available as of the analysis cutoff. Exclude later snapshots and records whose identity or availability time cannot be verified. If no eligible evidence remains, apply FR-OPT-05.

The recorded tradeoff is as follows. Historical coverage decreases when the provider cannot establish what was known at the time. The verifier measures ineligible evidence records passed to the analyst in cutoff and identity fixtures. The registered threshold is `0`. Evidence: OPT-T6 in docs/code-governance/verification-constraints.md.

**FR-DEB-01**  Let both researchers speak once in the opening round. From round two onward, evaluate progress only after both have spoken. End the debate early when neither side introduces evidence new to this debate nor gives a first substantive reply to a previously unanswered opposing argument. Record the reason for early termination and pass the complete debate history to the Research Manager. The configured maximum number of rounds remains binding.


The recorded tradeoff is as follows. Ending repeated exchanges saves debate turns. Waiting for a full round gives both sides a chance to contribute. The verifier measures scripted cases with an incorrect next speaker, stop round, termination reason or manager history. The registered threshold is `0`. Evidence: DEB-T1 through DEB-T5 in docs/code-governance/verification-constraints.md.

**FR-RPT-01**  Each consolidated stock report shall display one Company Background section after its header and before analyst reports, regardless of the analysts selected. Show the available company name, industry and a one- or two-sentence business description from the source. Omit missing fields. If no eligible fields are available, display an unavailable notice and complete the export. Apply the existing historical-date policy and show the same information in Markdown and requested HTML.


The recorded tradeoff is as follows. Omitting unsupported details keeps profiles factual even when the resulting introduction is brief. The verifier measures fixture exports failing the expected section count, placement, content or completion checks. The registered threshold is `0`. Evidence: RPT-T1 through RPT-T4 in docs/code-governance/verification-constraints.md.

**FR-TOK-01**  For each CLI or web analysis, start the usage total at zero. After each completed model call across all agents, add its provider-reported input and output token counts. On the first total strictly greater than the threshold, display one warning in the active interface with the total and threshold. Continue the analysis through normal report generation. The threshold defaults to 100000 tokens and accepts a positive integer override via TRADINGAGENTS_TOKEN_WARNING_THRESHOLD in .env.


The recorded tradeoff is as follows. The user can finish the analysis after a warning, so further model calls may consume more tokens. The verifier measures scripted runs with incorrect warning count, timing, displayed values or report completion. The registered threshold is `0`. Evidence: TOK-T1 and TOK-T2 in docs/code-governance/verification-constraints.md.

**FR-CIT-01**  Before the debate, number the body paragraphs of each analyst report supplied to the researchers. Each bull or bear argument drawing on a report shall carry the cited paragraph IDs beside that argument. Preserve the IDs on source paragraphs and arguments in consolidated Markdown and HTML. Mark any unknown reference as invalid and any argument lacking a reference as uncited. Continue the debate in both cases.


The recorded tradeoff is as follows. ID checks let readers locate the original wording. Readers judge how well it supports an inference. The verifier measures offline cases with a misplaced, ambiguous or wrongly flagged citation, inconsistent export, or interrupted debate. The registered threshold is `0`. Evidence: CIT-T1 through CIT-T3 in docs/code-governance/verification-constraints.md.

**FR-WEB-01**  The local web command shall start the service, print its local URL and open that URL in the default browser once ready. On one page the user can choose ticker, analysis date, configured provider, quick and deep models, analysts, research depth and report language. Apply the existing input validation and defaults, including FEAT-01 selection. Allow one active analysis at a time.

The recorded tradeoff is as follows. Using locally configured credentials and provider defaults keeps browser setup short. The verifier measures incorrect launches, accepted invalid submissions or duplicate starts. The registered threshold is `0`. Evidence: WEB-T1 in docs/code-governance/verification-constraints.md.

**FR-WEB-02**  During analysis the page shall show the same user-visible agent statuses, messages, tool activity, intermediate reports, debate turns, plans, decisions and reported token usage as the CLI for the same run events. Display each new item as it becomes available, once, with its role or source. Earlier output remains readable. On failure show the reason, preserve output and allow retry.

The recorded tradeoff is as follows. Event-level updates let readers follow the run without requiring token-by-token text streaming. The verifier measures scripted runs with missing, duplicated, premature or mismatched output or a failed retry flow. The registered threshold is `0`. Evidence: WEB-T2 and WEB-T3 in docs/code-governance/verification-constraints.md.

**FR-WEB-03**  On success the same page shall show the ticker, analysis date and final rating, display the full HTML report and offer the corresponding Markdown download. Both artifacts must belong to the completed run.

The recorded tradeoff is as follows. Reusing the report exporter keeps both formats consistent with the CLI. The verifier measures completed runs displaying incorrect metadata or serving artifacts from a different run. The registered threshold is `0`. Evidence: WEB-T4 in docs/code-governance/verification-constraints.md.

**QA-WEB-01**  Repeated reads with the same event cursor shall preserve the same ordered events without adding duplicates.

The recorded tradeoff is as follows. One cursor per run adds state but preserves a reader’s position. The verifier measures duplicate events in the repeated-cursor fixture. The registered threshold is `0`. Evidence: test/offline/test_web_events.py::test_a_repeated_snapshot_does_not_duplicate_prior_events.

**PERF-WEB-01**  The first published event shall be readable before a paused analysis completes.

The recorded tradeoff is as follows. Incremental delivery requires keeping the event stream in memory. The verifier measures fixture runs requiring graph completion before first delivery. The registered threshold is `0`. Evidence: test/offline/test_web_events.py::test_the_first_event_is_visible_before_the_run_finishes.

**COST-WEB-01**  Reviewing or downloading a completed report shall start zero additional analyses.

The recorded tradeoff is as follows. Retaining per-run artifacts consumes local disk space. The verifier measures additional graph runs triggered by review and download. The registered threshold is `0`. Evidence: test/offline/test_web_reports.py::test_viewing_and_downloading_after_completion_starts_no_new_run.

**GOV-DEP-01**  Direct imports of market vendor libraries must stay within the data layer.

The recorded tradeoff is as follows. New consumers must use an adapter even when a direct vendor call would be shorter. The verifier measures vendor imports outside permitted modules under the existing architecture fitness test. The registered threshold is `0`. Evidence: test/offline/test_layering.py::test_vendor_libraries_are_imported_only_by_the_data_layer.

**SEC-OPT-01**  The options evidence boundary must reject observations for another instrument or an unverifiable or later observation time before model input.

The recorded tradeoff is as follows. Historical coverage falls when the data source cannot establish the observation time. The verifier measures disallowed observations reaching the accepted fixture set. The registered threshold is `0`. Evidence: test/offline/test_options_data.py::test_adapter_keeps_only_matching_and_cutoff_eligible_records.

### Verification results and observed limitations

These are historical feature-round observations. Test counts describe their own revision and environment. The final local result is reported separately.

#### FEAT-01

| Case | Implemented evidence | Result |
| --- | --- | --- |
| OPT-T1 · FR-OPT-01 | `test_options_analyst.py::test_stock_defaults_include_the_original_four_plus_options`, `::test_fresh_stock_cli_preselects_five_and_saved_four_stays_four`, `::test_crypto_defaults_exclude_options`, `::test_saved_preferences_keep_the_original_four_and_drop_options_for_crypto`, `::test_explicit_options_only_and_original_four_selections`, `::test_deselected_options_makes_no_lookup_or_report` | Passed |
| OPT-T2 · FR-OPT-02 | `test_options_analyst.py::test_rendered_chain_reaches_the_options_model_input`, `::test_options_only_run_still_reaches_a_decision`; `test_options_data.py::test_rendered_evidence_contains_the_approved_indicator_set` | Passed |
| OPT-T3 · FR-OPT-03 | `test_options_analyst.py::test_options_report_reaches_bull_bear_and_three_risk_debaters`, `::test_deselected_options_report_is_absent_not_invented`, `::test_options_only_run_still_reaches_a_decision` | Passed |
| OPT-T4 · FR-OPT-04 | `test_options_analyst.py::test_options_report_reaches_cli_state_log_and_report_tree`, `::test_baseline_state_without_options_field_still_exports`, `::test_blank_options_report_writes_no_section`, `::test_cli_complete_report_shows_options` | Passed |
| OPT-T5 · FR-OPT-05 | `test_options_analyst.py::test_unavailable_notice_reaches_outputs_without_a_model_call`, `::test_unavailable_notice_carries_no_inferred_signal`; `test_options_data.py::test_historical_run_falls_back_to_unavailable_through_the_router` | Passed |
| OPT-T6 · INV-OPT-01 | `test_options_data.py::test_adapter_keeps_only_matching_and_cutoff_eligible_records`, `::test_date_only_snapshot_is_eligible`, `::test_record_at_cutoff_is_eligible`, `::test_duplicate_contract_keeps_latest_eligible_observation`, `::test_naive_timestamp_is_unverifiable`, `::test_only_rejected_records_trigger_unavailable`; `test_options_analyst.py::test_future_snapshot_never_reaches_the_options_model` | Passed |
| Live provider check | `test/live/test_options_yfinance_live.py` against the current yfinance option chain and a historical request | 2 passed |

Offline regression: `python -m pytest -q` reported `1443 passed, 6 skipped, 3 deselected, 100 subtests passed`. Structural check: `ruff check src test` reported no findings. The live file was run separately with `-m integration`.


#### FEAT-02

| Requirement | Component | Test or evidence | Runtime monitor |
| --- | --- | --- | --- |
| FR-DEB-01 | Bear-researcher progress judgement (`agents/debate_progress.py`), research-debate state, bull/bear router (`graph/conditional_logic.py`) and Research Manager handoff | DEB-T1 through DEB-T5; semantic fixture set (SEM-01, SEM-02, SEM-03, SEM-04, SEM-05a, SEM-05b, SEM-06) | `progress_outcome`, `progress_round` and `progress_reason` in the debate state and saved run log; ordered speaker history |

Implementation on branch `CS5351`. The end-to-end behaviour was verified offline; the semantic accuracy of the live judge is **not yet evaluated** (see the gap note below).

| Case | Implemented evidence | Result |
| --- | --- | --- |
| DEB-T1 · FR-DEB-01 | `test_debate_early_stop.py::test_deb_t1_opening_round_gives_bear_then_begins_round_two`, `::test_after_bull_speaks_in_round_two_the_bear_still_gets_a_turn` | Passed |
| DEB-T2 · FR-DEB-01 | `test_debate_early_stop.py::test_deb_t2_second_round_repetition_stops_after_the_bear_speaks`, `::test_cap_stop_is_not_labelled_no_progress` | Passed |
| DEB-T3 · FR-DEB-01 | `test_debate_early_stop.py::test_deb_t3_new_report_fact_continues_to_round_three` | Passed |
| DEB-T4 · FR-DEB-01 | `test_debate_early_stop.py::test_deb_t4_first_reply_continues_to_round_three` | Passed |
| DEB-T5 · FR-DEB-01 | `test_debate_early_stop.py::test_deb_t5_cap_one_hands_off_after_one_round`, `::test_deb_t5_cap_two_hands_off_after_two_rounds`, `::test_different_caps_keep_independent_final_rounds` | Passed |
| Judgement scheduling / cap precedence | `::test_judgement_is_scheduled_only_for_complete_rounds_between_two_and_cap`, `::test_bear_node_judges_only_round_two_not_the_opening_round`, `::test_bear_node_does_not_judge_at_or_after_the_cap` | Passed |
| Reason before/after manager, persistence | `::test_bear_node_records_no_progress_reason_before_the_manager_runs`, `::test_manager_preserves_the_reason_it_was_given`, `::test_manager_preserves_full_history_on_early_stop`, `::test_saved_run_log_records_outcome_and_reason` | Passed |
| UNKNOWN / fail-open / stale / old-state | `::test_failed_judgement_becomes_unknown_without_a_freetext_retry`, `::test_unknown_outcome_continues_and_keeps_speaker_order`, `::test_stale_no_progress_does_not_stop_the_opening_round`, `::test_stale_no_progress_does_not_stop_a_later_round_without_a_current_judgement`, `::test_older_state_without_progress_fields_still_routes_and_logs` | Passed |
| Structured contract (`classify_judgement`) | `::test_contract_clean_progress_maps_to_progress`, `::test_contract_confirmed_repetition_maps_to_no_progress`, `::test_contract_malformed_inconsistent_or_uncertain_is_unknown` (8 payload variants), `::test_contract_explicit_unknown_passes_through`, `::test_contract_schema_file_matches_rules` | Passed |
| FEAT-01 regression (options→researchers) | `::test_options_report_still_reaches_the_bull_researcher`, `::test_options_report_still_reaches_the_bear_researcher`; `test_options_analyst.py` and `test_options_data.py` unchanged and green | Passed |
| Semantic fixture well-formedness | `test_debate_semantics_eval.py::test_fixture_is_well_formed` (7 cases, labels validated) | Passed |

Offline regression: `python -m pytest -q` reported `1483 passed, 6 skipped, 4 deselected, 100 subtests passed` (1443 prior + 40 FEAT-02). FEAT-02 file alone: `40 passed, 1 deselected`. Structural check: `ruff check` on the changed src files and the two new test files reported no findings.

**Test-fixture correction recorded.** Six bear-node judge-scheduling tests and their helper initially assumed judgement on the *input* count (pairs "complete at even input counts"), which conflicted with the authoritative rule that the bear node receives the count before its turn and increments it. The rule is: judgement happens only after the bear completes a pair, when the resulting (post-increment) count is even and `4 <= new_count < 2 * max_debate_rounds`. The tests were corrected with explicit `cap=3` for round-two judgement and pre-bear input counts 3 (round two) and 5 (round three); assertions were strengthened (e.g. asserting the resulting `count == 4`), not weakened. Production logic was not changed to satisfy the tests.

**Live semantic-evaluation status (not a pass).** The judge runner is gated behind `DEBATE_EVAL_LIVE=1` (renamed from a `TRADINGAGENTS_*` name, which `test/conftest.py` blanks at import time) and uses the CityU DeepSeek endpoint (`deepseek` provider, base URL `https://llm.cs.cityu.edu.hk/v1`, model `CS5351/DeepSeek-V4-Flash`) via `DebateJudge.evaluate()`.

A single-request guarded probe, `test/live/test_debate_judge_cityu_probe.py`, was run against that endpoint and succeeded: `1 passed, 1 warning`; the model returned a valid `NO_PROGRESS` judgement, confirming structured output works on this endpoint.

The **first full seven-case semantic evaluation was then run and failed** (`DEBATE_EVAL_LIVE=1 python -m pytest test/offline/test_debate_semantics_eval.py -m integration -q` → `1 failed, 7 deselected, 1 warning, 10.77s`). Five mismatches were reported:

Analysis: these were **fixture/evaluation-design defects, not established model errors**. The captured run output is `transcripts/FEAT-02-live-eval-2026-11-22.txt`. SEM-04's original text introduced new facts (fixed contracts; contracts expiring) though it was labelled `new_evidence:false`; SEM-01's bear reused the bull's same-pair margin fact; SEM-02's bear directly rebutted the bull's current point (a defensible first reply); SEM-06's history A already contained the very reply under judgement and history B was never scored. The fixtures were corrected (SEM-01 bear → an independent new fact; SEM-02 bear → independent evidence, no same-pair rebuttal; SEM-04 → text that reuses only history facts; SEM-06 → history A before the reply, history B after it, both scored with the same reply text; approved labels A `{new:true, first_reply:true}`, B `{new:false, first_reply:false}`). These corrections are recorded as necessary precisely because the original fixtures did not isolate the property each case claimed to test.

**Second live evaluation (not a pass).** After the first corrections the seven-case evaluation was run again: `DEBATE_EVAL_LIVE=1 python -m pytest test/offline/test_debate_semantics_eval.py -m integration -q` → `1 failed, 7 deselected, 1 warning, 16.40s`. One mismatch remained: **SEM-04 bear** got `{new_evidence:false, first_reply:false}` vs expected `{new_evidence:false, first_reply:true}`. The bear turn then restated the forecast ("rising input costs have not stopped threatening those margins") rather than addressing the bull's observed co-movement point, so `first_reply=false` was defensible for that text — another fixture-text defect, not an established model error. The SEM-04 bear turn was revised (delayed cost pass-through presented as a *possible* explanation, using only history facts) to earn a first substantive reply without new evidence. The live evaluation has **not** been re-run since; real semantic accuracy remains unverified.

**Third live evaluation (not a pass).** After the SEM-04 bear revision, the evaluation was run a third time: same command → `1 failed, 7 deselected, 1 warning, 16.05s`. Mismatches: **SEM-02 bull** got `first_reply:true` vs expected `false`; **SEM-02 bear** got `new_evidence:false` vs expected `true`; **SEM-04** returned **no structured judgement** (`DebateJudge.evaluate()` returned `None`). Diagnosis: (a) SEM-02 — the labels are defensible on the text, but the model read the bull's moat/brand-partnership claim as a reply to the prior "valuation is stretched" and read the bear's distributor fact as not-new; this is model interpretation, not a clear fixture defect. (b) SEM-04 `None` — `evaluate()` returns `None` only when the structured call yields no parsed `DebateJudgement` (or has no binding); the binding is proven (other cases in the same run parsed, and the earlier probe returned a valid judgement), and a raised exception would have produced a traceback rather than "None". So SEM-04's `None` is a **per-call structured-output miss / provider variability**, not a demonstrated production error or an exception. Fixture changes to chase a pass have been **discontinued**; the remaining failures are recorded as unresolved limitations. Three runs, none passed; semantic-quality acceptance remains unverified.


#### FEAT-03

| Case | Implemented evidence | Result |
| --- | --- | --- |
| Initialization retention | `test_company_background.py::test_initialization_retains_the_cleaned_profile_from_one_lookup`, `::test_initialization_retains_only_the_cleaned_profile_fields`, `::test_initialization_omits_placeholder_profile_values` (6 placeholders) | Passed |
| Init compatibility / no second lookup | `::test_initialization_reuses_the_cached_profile_without_a_second_lookup` | Passed |
| Graph retention → `save_reports` | `::test_the_retained_profile_survives_the_graph_and_reaches_save_reports` | Passed |
| Graph retention → CLI `_offer_reports` | `::test_the_retained_profile_reaches_the_cli_offer_reports_entry` | Passed |
| No Fundamentals Analyst required | `::test_a_run_without_the_fundamentals_analyst_still_carries_a_background` | Passed |
| Run-log persistence (RPT-LOG) | `::test_the_run_log_persists_company_identity` | Passed |
| RPT-T1 placement | `::test_exactly_one_background_sits_after_the_header_and_before_analysts` | Passed |
| RPT-T1 content | `::test_full_profile_shows_name_industry_and_complete_description` | Passed |
| RPT-T2 | `::test_name_only_profile_omits_missing_labels_and_content` | Passed |
| RPT-T4 | `::test_a_historical_run_labels_the_current_name_and_hides_undated_details`, `::test_a_historical_run_without_a_name_shows_the_notice_and_leaks_no_undated_fields` | Passed |
| RPT-T3 | `::test_no_profile_shows_an_unavailable_notice_and_still_exports` (absent/empty) | Passed |
| Old state / no export lookup | `::test_old_state_without_company_identity_exports_without_lookup_or_cache`, `::test_export_performs_no_additional_lookup_even_when_identity_is_present` | Passed |
| Sentence retention/trimming | `::test_business_description_keeps_one_or_two_complete_source_sentences` (5 cases), `::test_the_description_is_not_truncated_mid_sentence` | Passed |

Offline regression: `python -m pytest -q test/offline` reported `1522 passed, 1 skipped, 1 deselected, 100 subtests passed`. Targeted regressions (layering, reporting, report_html, instrument_identity, undated_tools_as_of, options_analyst): `84 passed`. Structural: `ruff`/`pyflakes` were not installed, so no lint run is claimed; `py_compile` of the changed modules succeeded and the layering test passed.

Three confirmed review issues were corrected; the approved test file was extended first (blob `1023b4c964fa96bf7d5f734f1f97632df58c0b43`) and then the implementation was changed. The 28 original approved tests are unchanged; the 6 correction tests are listed below.

| Correction | Issue | Evidence | Result |
| --- | --- | --- | --- |
| Literal text parity | Markdown interpolated raw profile text while HTML escaped it | `::test_literal_profile_text_is_shown_the_same_way_in_both_formats` (3 cases: `*Group*`, `A&B <Holdings>`, `_Co_ & <b>x</b> [link](y)`) | Passed |
| Optional state field | `company_identity` appeared in `__required_keys__` | `::test_company_identity_is_an_optional_state_field` | Passed |
| Legacy-state export | a state without `company_identity` must still export | `::test_legacy_state_without_company_identity_still_exports` | Passed |
| Custom context hook | `create_run_state` bypassed `resolve_instrument_context` overrides | `::test_initialization_respects_a_custom_resolve_instrument_context` | Passed |

Correction verification: FEAT-03 file `34 passed`; full offline `python -m pytest -q test/offline` reported `1528 passed, 1 skipped, 1 deselected, 100 subtests passed`; targeted (layering, reporting, report_html, instrument_identity, undated_tools_as_of, options_analyst, portfolio_context) `113 passed`; `py_compile` of the changed modules OK; `ruff`/`pyflakes` still unavailable (no lint run claimed). A direct probe confirmed a failed identity resolution performs one vendor attempt and no immediate retry.


#### FEAT-04

The CLI and shared-handler evidence is recorded below. The browser rows in TOK-T1 and TOK-T2 await FEAT-06 integration.

| Evidence | Result |
| --- | --- |
| TOK-T1: strict crossing, immutable values and an immediate terminal warning while a later model call is pending | Passed in `test_token_warning.py` and `test_cli_token_warning.py`; subsequent calls and both report exports completed. |
| TOK-T2: default threshold, missing usage and two consecutive CLI runs | Passed in `test_cli_token_warning.py`; each run used a distinct handler and warned at 100001. |
| Supporting cases: concurrent completions, receiver failure, environment validation, independent output cap and checkpoint identity | Passed in `test_token_warning.py`; real graph coverage included parallel analysts, both model tiers and the structured debate judge. |
| Browser activity view | Pending FEAT-06. Shared receiver tests exercised the interface without a browser. |

On Python 3.12.14 the two feature files passed all 20 cases. The full offline suite recorded 1548 passed, 1 skipped, 1 deselected and 100 subtests passed. The default local suite recorded 1548 passed, 1 skipped, 5 deselected and 100 subtests passed.

Pre-commit correction: warning rendering at 40, 50 and 80 columns preserved both values. The corrected feature suite passed 23 tests and the full offline suite passed 1551 tests and 100 subtests (1 skip, 1 deselection).


#### FEAT-05

| Case | Implemented evidence | Result |
| --- | --- | --- |
| CIT-T1 · FR-CIT-01 source numbering | `test_debate_citations.py` and `test_debate_citations_exports.py`: prefixes `MKT/SEN/NWS/FUN/OPT`, numbering from `01`, deselected analysts unnumbered, labels reaching prompt and both exports | Passed |
| CIT-T2 · FR-CIT-01 per-argument notices | Same files: three-paragraph bull/bear turn, valid pair, `Invalid citation`, `No citation provided`, notices beside their own claim in Markdown and HTML, individual and consolidated reports agreeing, manager reading the recorded history | Passed |
| CIT-T3 · FR-CIT-01 judge input | Same files: the FEAT-02 judge receives the recorded annotated turns | Passed |
| CIT-T1..T9 contract, state ownership, layout, exports, run log, checkpoint resume | `test_debate_citations_exports.py`: graph layout unchanged, Options/FEAT-02/03 compatibility, run log fields, resume | Passed |
| Six reviewed defects (explicit citation instruction, `NotRequired` fields, IDs past 99, headings excluded, intact unnumbered fences in prompt and exports, per-speaker turn numbering) | `test_debate_citations_supplementary.py` | Passed (9) |
| Rendering/segmentation regressions: heading preserved unnumbered without duplicating a body (prompt, Markdown, HTML); prose above an opening fence kept and numbered; debate fence attaching to its claim, with the same citation, validity and notice in both spacing variants | `test_debate_citations_regressions.py` | Passed (7) |

Approved test hashes verified with `shasum -a 256` after implementation. The three untouched approved files match their recorded hashes; the regression file carries the approved two-case correction, `e93e099bca763a0ba9d25b01afdb66a2539bea92de13fad29bccdae239bfc0d1` → `b23f62899b96fec3ed8c77932c44205f3a1979993ceca60f67c3407592e216d2`.

| Check | Result |
| --- | --- |
| Four FEAT-05 test files | 63 passed |
| Full offline suite | 1614 passed, 1 skipped, 1 deselected, 100 subtests passed |
| `ruff check src/` and the four FEAT-05 files | All checks passed |

The two contradictions reported on 2026-11-23 are resolved by the approved test corrections: the claim's `FUN-01` is valid in its own fixture and takes no notice, and the two fence-spacing variants are each asserted to preserve their exact input while resolving the same citation identically.

Note: the token-warning failure reported in earlier rounds does not reproduce in the fresh editable environment (21 passed). It is specific to the conda environment, where a stale installed `cli` package shadows the repository copy (`ImportError: cannot import name 'render_live_layout' from 'cli.display'`).


#### FEAT-06

| Observation | Evidence and implication |
| --- | --- |
| Baseline regression | Before adding web tests the project recorded 1,620 offline passes. Implementing the first 27 web cases brought that round to 1,647. These results establish the original run, event and export contracts. |
| Subscription sign-in | Six additional checks reproduced the empty selectors, verified the signed-in model list and covered signed-out and provider-error paths. The feature round reached 1,653 offline passes. |
| Long-running analysis display | Four later checks covered ordered events, the final event and collapsible page markup. The recorded round reached 1,657 offline passes. Readability, scroll position and actual clicks also need a browser observation. |
| Report source navigation | Preview navigation must preserve saved-file bytes and lead to the unique source paragraph in the analyst reports. A repeated label in the decision section must remain a reference to that source. |

### Final local regression boundary

The pre-correction run of the offline suite produced 1,656 passes, one failure, one skip, one deselection and 100 passing subtests. The failure was a duplicate source target in the web preview. The optional-provider skip concerned langchain_aws. The live semantic evaluation was excluded from this offline command. Prior green feature-round counts do not supersede a failing assertion on a later working tree.


The corrected preview obtains target IDs only inside the generated Analyst Team Reports section. It creates one anchor per source paragraph, links repeated references in paragraphs and lists, and preserves unknown IDs as text. The regression fixture that previously found two targets now passes without changing its assertions. After adding the course-gate tests and moving the real judge evaluation to the live suite, the full offline run passed 1,663 tests and 100 subtests, with one optional-provider skip. This is local deterministic evidence. Hosted merge protection, independent review and live model quality require separate evidence.
