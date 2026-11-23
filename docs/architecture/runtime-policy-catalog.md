# Runtime policy catalog

| Failure trigger | Detection | Deterministic response | Evidence or monitor |
| --- | --- | --- | --- |
| No chain, unsupported stock, or provider failure | No usable observations for the selected stock and date | Publish an unavailable notice, retain its stock and date context, and continue the graph | CLI, five recipient inputs and saved report (OPT-T5) |
| Later or unverifiable observations | Check identity and availability time before building model context | Discard those records. Analyze the eligible subset or use the unavailable path if it is empty | Adapter output compared with fixture timestamps (OPT-T6) |
| Analyst deselected | Explicit active analyst list omits options | Skip options data access, inference and report output | Selected roles and tool calls (OPT-T1) |
| Research-debate opening round | Fewer than one complete bull/bear pair has been recorded | Do not evaluate early stopping; let both researchers speak | DEB-T1 |
| Research-debate pair has no confirmed progress | A completed pair is classified `NO_PROGRESS` for its own round | Record the fixed stop reason, retain the complete history and hand off to the Research Manager | DEB-T2 |
| Progress judgement is missing, malformed, inconsistent or uncertain | The structured result cannot establish a confident `PROGRESS` or `NO_PROGRESS` outcome | Classify it as `UNKNOWN` and continue the debate, subject to the configured cap | `test_debate_early_stop.py` malformed/uncertain and failed-judgement cases |
| Research-debate cap reached | The configured number of complete bull/bear rounds has been recorded | Stop without another judgement and hand the full history to the Research Manager; the cap takes precedence over progress | DEB-T5 |
| Company profile fields unavailable | The retained run state has no eligible name, industry or description for the requested date | Render the explicit Company Background unavailable notice and continue exporting the analysis and final decision | RPT-T3 |
| Token usage absent from a completed model response | No usage metadata | Keep the measured total and continue. | TOK-T2 |
| Token warning receiver fails | Receiver raises while publishing the first crossing | Preserve the crossing snapshot, log the failure, and continue without retrying the receiver. | FR-TOK-01 receiver failure test and application log |
| Research argument cites an ID absent from this run | Citation validation cannot resolve the written ID against the stored paragraph map | Keep the written ID visible, append `Invalid citation` to that argument and continue the debate | CIT-T2 |
| Research argument contains no paragraph ID | Per-argument citation extraction returns no IDs | Append `No citation provided` to that argument and continue the debate | CIT-T2 |
| Web submission is empty or invalid | Server-side validation rejects the submitted configuration | Start no analysis and return an actionable validation response | WEB-T1 |
| Web start is submitted again while a run is active | `RunManager` already owns a running analysis | Return the existing run ID; do not start a second graph run | WEB-T1 and `test_web_events.py` |
| Web analysis fails after publishing events | The graph runner raises while the run is active | Retain published events, expose the failure reason, mark the run failed and allow a later retry with a new run ID | WEB-T3 |
| Requested web port is occupied | Loopback bind fails before service readiness | Print an actionable command using another port instead of a traceback | WEB-T1 and `test_web_launcher.py` |
