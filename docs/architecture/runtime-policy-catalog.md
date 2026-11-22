# Runtime policy catalog

| Failure trigger | Detection | Deterministic response | Evidence or monitor |
| --- | --- | --- | --- |
| No chain, unsupported stock, or provider failure | No usable observations for the selected stock and date | Publish an unavailable notice, retain its stock and date context, and continue the graph | CLI, five recipient inputs and saved report (OPT-T5) |
| Later or unverifiable observations | Check identity and availability time before building model context | Discard those records. Analyze the eligible subset or use the unavailable path if it is empty | Adapter output compared with fixture timestamps (OPT-T6) |
| Analyst deselected | Explicit active analyst list omits options | Skip options data access, inference and report output | Selected roles and tool calls (OPT-T1) |
| Token usage absent from a completed model response | No usage metadata | Keep the measured total and continue. | TOK-T2 |
| Token warning receiver fails | Receiver raises while publishing the first crossing | Preserve the crossing snapshot, log the failure, and continue without retrying the receiver. | FR-TOK-01 receiver failure test and application log |
