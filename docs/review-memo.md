# Shared-branch review memorandum

## FEAT-01 — Options Analyst

**Specification and architecture.** FR-OPT-01 through FR-OPT-05, INV-OPT-01 and ADR 001 require a separate selectable analyst, a report delivered to five debate participants, cutoff-eligible evidence, exports and an unavailable-data fallback. The data-layer adapter checks instrument identity and observation time before model input. Graph, CLI and report writer share the `options_report` field.

**Code and tests.** OPT-T1 through OPT-T6 cover selection, report evidence, delivery, exports, no data and cutoff cases. The recorded round added 31 offline tests; its full suite reported 1,443 passed, 6 skipped, 3 deselected and 100 subtests passed. The live current-chain and historical-refusal checks reported 2 passed; Ruff was clean.

**Security and efficiency.** Vendor calls stay in the data layer; no eligible chain means no options model call. No new runtime dependency or credential exposure was reported. Current yfinance chains cannot prove historical availability.

**Verdict: APPROVE.**

## FEAT-02 — Research debate early stop

**Specification and architecture.** FR-DEB-01 requires both researchers in the opening round, paired progress checks later, a bounded maximum, an early-stop reason and complete manager history. The structured quick-tier judge supplies advisory progress; deterministic routing continues on uncertainty. Risk debate routing remains unchanged.

**Code and tests.** DEB-T1 through DEB-T5 exercise turn order, routing, the cap, termination reason and handoff. The recorded feature round reported 46 passing targeted tests and a full offline suite of 1,489 passed, 6 skipped, 5 deselected and 100 subtests passed; Ruff was clean.

**Security and efficiency.** The judge reuses the configured model client and structured-output helper; no new provider or credential path was added. An early stop can save turns, while the configured cap still binds. This offline routing acceptance does not establish live-model semantic accuracy; that separate evaluation remains documented in the trace matrix and evaluation logbook.

**Verdict: APPROVE.**

## FEAT-03 — Company background

**Specification and architecture.** FR-RPT-01 requires one background section between the header and analyst reports in Markdown and HTML. The graph retains cleaned identity at initialization; export uses saved run data rather than fetching a new profile.

**Code and tests.** After corrections to literal-text parity, optional state and the context override, 34 feature tests and a full offline suite of 1,528 passed, 1 skipped, 1 deselected and 100 subtests passed were reported. Haobin Yan checked an AAPL run and both exports. Earlier CI for `ca6bb65` (run 45026962649) failed Ruff; an approved import-only correction then passed local Ruff and offline checks. That historical failed run is separate from the later CI pass confirmed by the user.

**Security and efficiency.** A single identity resolution is retained; exporters add no provider/model call. HTML escaping and CSP remain in place, with missing and historical data covered offline.

**Verdict: APPROVE.**

## FEAT-04 — Token warning

**Specification and architecture.** FR-TOK-01 uses one callback per analysis to warn once after cumulative reported token usage strictly exceeds the configured threshold. The warning is advisory and does not change model output limits or interrupt the run.

**Code and tests.** The post-correction round reported 23 feature tests, 173 targeted tests and 1,551 offline tests passed, with 1 skip, 1 deselection and 100 passing subtests. Review found threshold clipping at narrow terminal widths; approved 40-, 50- and 80-column cases preceded the fix. Ruff and whitespace checks passed.

**Security and efficiency.** The existing accumulator counts provider-reported tokens without polling or another inference call. Fixtures use no credentials; a warning-delivery failure does not interrupt analysis.

**Verdict: APPROVE.**

## FEAT-05 — Debate paragraph citations

**Specification and architecture.** FR-CIT-01 numbers analyst paragraphs, checks the IDs written by each researcher, and preserves valid, invalid and uncited notices through the debate and Markdown/HTML exports. Deterministic code owns ID matching; the researchers own the argument text.

**Code and tests.** Four approved feature test files reported 63 passed; later notice-deduplication regressions passed. The recorded later full offline suite reported 1,620 passed, 1 skipped, 1 deselected and 100 subtests passed. The live sample produced six researcher turns and resolved 139 of 139 written IDs. The original AI-assisted assessment and its rows remain under `docs/evaluations/feat05-live/`.

**Security and efficiency.** Validation uses a run-local paragraph map without an added production provider call. HTML escaping/CSP remain; saved live artifacts were checked for key leakage.

**Verdict: APPROVE.**

## FEAT-06 — Local web interface

**Specification and architecture.** FR-WEB-01 through FR-WEB-03 and ADR 003 call for one local page using CLI configuration, the shared graph stream and exporter. Run IDs and cursors preserve event order and associate each preview and download with its completed analysis.

**Code and tests.** Seven web test files reported 37 passing cases. Browser review exposed ChatGPT subscription model selection and a long process view; tests and corrections followed. A later preview regression found duplicate source targets for one citation. After the analyst-only target correction, the recorded integrated suite reported 1,663 passed and 100 subtests passed, with one optional-provider skip.

**Security and efficiency.** The server binds loopback, keeps credentials on the host, and uses one graph and export per run. HTTP fixtures allow loopback only; report rendering retains safe HTML handling.

**Verdict: APPROVE.**