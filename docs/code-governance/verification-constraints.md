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

Proposed offline cases. Use fixed profile data and exercise the existing CLI and Python export paths. Compare the visible section text across formats.

| Case | Input | Expected export |
| --- | --- | --- |
| RPT-T1 | Full profile with a name, industry and two-sentence description. Omit Fundamentals Analyst from the selection. | Each format contains one background section after the header and before the analyst reports. Both show the fixture fields and the same description. |
| RPT-T2 | Profile contains only a company name. | Both sections show just the name. The rest of the report exports successfully. |
| RPT-T3 | No profile fields are available. | Both sections show an unavailable notice. The analysis and final decision still appear in the export. |
| RPT-T4 | Historical analysis with only a current name, current industry and current business description. | Both sections label the name as current and omit the undated industry and business description. |
