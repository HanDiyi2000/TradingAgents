# Verification constraints

Reference a requirement or invariant in each new test. Cover every fit criterion and include a violation test for each invariant and a negative test per feature. Have a human approve the proposed tests before implementation.

Verify structural boundaries and permissions, run all previous regression suites, and measure behavior against approved thresholds. Record failures and rerun evidence in the review memo.

## Options Analyst — proposed offline acceptance cases

Review and approve these cases before implementation. Use fixed option-chain observations, a recording model and the existing offline graph. Each case below describes expected evidence.

| Case | Setup and assertion |
| --- | --- |
| OPT-T1 · FR-OPT-01 | Check fresh CLI and Python stock defaults include exactly the original four plus options. Repeat with explicit options-only and original-four selections, including saved preferences. Verify selected nodes match exactly. With options off, count zero options fetches, calls and exported sections. |
| OPT-T2 · FR-OPT-02 | Supply an eligible option-chain observation with a distinctive expiry, strike and quoted value. Assert exactly one independent report for the selected stock/date and check its evidence against the fixture. Inspect the analyst input for the option-chain observation. |
| OPT-T3 · FR-OPT-03 | Tag the options report. Capture the actual model inputs for the bull, bear, aggressive, neutral and conservative roles and check all five for the tag. Repeat with only options selected. Trace scripted debate and plan outputs through the managers and trader to a decision. |
| OPT-T4 · FR-OPT-04 | Use the tagged report. Check CLI completion and report panel, final state and saved JSON log. Exercise CLI and Python export and check the individual Markdown file, combined Markdown and requested HTML. Reopen a baseline output without the new field. |
| OPT-T5 · FR-OPT-05 | Replay an empty chain, unavailable provider and historical date without an eligible snapshot. Each run must expose the unavailable notice to all five direct consumers, show and save that notice, and produce a final decision. Check the notice carries no inferred options signal. |
| OPT-T6 · INV-OPT-01 | Inject a later snapshot into a historical run. Also exercise wrong-symbol and unknown-time records. Capture the adapter output: zero invalid observations may enter the analyst context. In a mixed fixture retain eligible observations, including one at the cutoff. With only rejected records verify the OPT-T5 fallback. |

Run the full prior offline suite alongside these cases in the implementation PR. Live-provider checks depend on provider selection and credentials.

## FEAT-02 — Research debate early stop (FR-DEB-01)

Proposed offline cases. Use scripted researcher turns and inspect the route after each turn.
For every termination, compare the Research Manager's input history with the full scripted exchange through the last bear turn.

| Case | Fixed exchange | Expected outcome |
| --- | --- | --- |
| DEB-T1 | Limit 3. Both sides state opening positions without citing evidence or answering a point. | Bull and bear each speak once. Round two begins. |
| DEB-T2 | Limit 3. In round two both repeat round-one facts and rephrase a rebuttal already made. | The bear still gets its turn. Stop after round two, record the no-progress reason and hand off without starting round three. |
| DEB-T3 | Limit 3. In round two one side cites a report fact unused in round one. Neither side answers a new point. | Begin round three. |
| DEB-T4 | Limit 3. Round two adds no facts, but one side addresses a specific opposing argument left unanswered in round one. | Begin round three. |
| DEB-T5 | Run with limit 1, then with limit 2 and fresh evidence in round two. | Hand off after exactly one and two complete rounds respectively. The configured cap applies in both cases. |

## FEAT-03 — Company background (FR-RPT-01)

Approved offline cases (test blob `821e88d24eae95fcd7f01bf094fb23a90bff52b2`). Use fixed profile data and a frozen test date; exercise the existing Python (`TradingAgentsGraph.save_reports`) and CLI (`run._offer_reports` with non-interactive flags) export paths. Compare the visible section text across formats.

| Case | Input | Expected export |
| --- | --- | --- |
| RPT-T1 | Full profile with a name, industry and two-sentence description. Omit Fundamentals Analyst from the selection. | Each format contains one background section after the header and before the analyst reports. Both show the fixture fields and the same description. |
| RPT-T2 | Profile contains only a company name. | Both sections show just the name; the Industry label and description are omitted. The rest of the report exports successfully. |
| RPT-T3 | No profile fields are available. | Both sections show an unavailable notice. The analysis and final decision still appear in the export. |
| RPT-T4 | Historical analysis with only a current name, current industry and current business description. | Both sections label the name as current and omit the undated industry and business description. |
| RPT-INIT | A full profile through run initialization, including a direct context call before it. | The cleaned profile is retained from a single lookup; the second resolution reuses the cache; `resolve_instrument_context` behaviour is unchanged. |
| RPT-RETENTION | A complete offline analysis; then both export entry points. | The retained profile survives the graph into final state and reaches both formats; the run log persists `company_identity`. |
| RPT-SENTENCE | Fixed summaries with two/three sentences, a decimal and a long first sentence. | One or two complete source sentences are kept, unsummarised, in both formats; no character cap truncates a sentence. |
| RPT-LITERAL (correction, blob `1023b4c9…`) | Profile text with Markdown markers and HTML-sensitive characters (`*Group*`, `A&B <Holdings>`, `_Co_ & <b>x</b> [link](y)`). | Both formats show the same literal source text; no emphasis, tags or links are produced in Markdown; HTML shows the same characters. |
| RPT-OPTIONAL (correction) | State schema inspection and a legacy state without `company_identity`. | `company_identity` is in `__optional_keys__` and not in `__required_keys__`; a legacy state exports with the notice and a fresh run still retains the field. |
| RPT-HOOK (correction) | A custom `resolve_instrument_context` override. | Initialization calls the override with `(ticker, asset_type, trade_date)`, its value reaches `instrument_context`, and exactly one vendor lookup retains the profile; a failed lookup is not retried. |

## FEAT-04 — Per-run token usage warning (FR-TOK-01)

Proposed offline cases. Feed scripted usage metadata from multiple agents through each entry point. Capture terminal warnings for CLI runs and browser activity warnings for web runs.

| Case | Setup | Expected outcome |
| --- | --- | --- |
| TOK-T1 | Set the threshold to 1000. Supply input/output pairs (700, 200), (80, 20), (60, 40) and (100, 100). | Cumulative totals are 900, 1000, 1100 and 1300. Exactly one warning appears, at 1100, showing 1100 used and a threshold of 1000. The final report is produced. |
| TOK-T2 | Leave the threshold unset. Run two analyses in the same process. In each, reach 100000, receive one completion with no usage metadata, then add one reported token. | Each analysis starts at zero, stays quiet through 100000, and warns once at 100001 with the default threshold of 100000. |

## FEAT-05 — Paragraph citations (FR-CIT-01)

Use fixed analyst reports and scripted turns. Inspect both researcher inputs and the exported Markdown and HTML. These cases are proposed for review before implementation.

| Case | Setup | Expected outcome |
| --- | --- | --- |
| CIT-T1 | Supply a fundamentals report with a heading and two distinct body paragraphs separated by a blank line. Bull cites the first and bear the second. Repeat with an options report added to the inputs. | Both researchers see FUN-01 and FUN-02 on the same original paragraphs in both runs. The heading has no ID. The options report starts at OPT-01. Each export contains one matching source paragraph per citation, with the ID also beside the correct argument. |
| CIT-T2 | Script a claim citing two valid paragraphs, one citing an absent FUN-99, and one with no citation. | Both valid references remain beside the first claim. The unknown ID carries an invalid-citation notice and the uncited claim carries a missing-citation notice in both exports. The debate reaches the Research Manager. |
| CIT-T3 | Below the round cap, bear first answers an outstanding bull argument using the same valid paragraph ID as bull. | Both citations resolve to that paragraph. FEAT-02 recognizes the first reply as progress. |

## FEAT-06 — Local web interface

Proposed offline cases use a local browser, a scripted graph and fixed report fixtures.

| Case | Setup and expected outcome |
| --- | --- |
| WEB-T1 · FR-WEB-01 | Observe the launcher opening the printed URL after readiness. Simulate a failed browser launch and open that URL manually. Verify the configuration form, default options analyst and quick/deep model choices. An empty ticker starts zero runs. Submit valid non-default selections twice rapidly and verify exactly one run receives those settings. |
| WEB-T2 · FR-WEB-02 | Replay the same events to CLI and web. Pause after a tool call, an analyst report and a bull turn. All three must already be visible in the browser, with later turns absent. Resume with a repeated snapshot, bear reply, stop reason, manager plan, trader proposal, three risk opinions and decision. Compare visible content and roles with the CLI at each checkpoint, checking prior turns remain visible once. Include options data or its unavailable notice, valid and invalid citations, token totals and one threshold warning. |
| WEB-T3 · FR-WEB-02 | Fail the graph after a published report. The page retains that report, shows the failure reason and allows a new analysis. Verify retry starts with its own events and token counters. |
| WEB-T4 · FR-WEB-03 | Complete two runs with different tickers and distinct report markers. For each, check ticker, date and rating, then match the preview and download to that run's HTML and Markdown exports. Check company background and numbered source paragraphs. After the second run, both artifacts must contain its marker. |
