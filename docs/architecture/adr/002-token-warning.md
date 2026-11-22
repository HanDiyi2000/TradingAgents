# ADR 002 — Account for token usage in the run statistics handler

Status: Implemented for the CLI. Browser integration awaits FEAT-06.

FR-TOK-01 counts both provider-reported token fields at model completion, across the existing graph and model callback chain. Missing usage contributes nothing. Each run owns one handler. The existing lock guards both accumulation and the first crossing when the total is strictly greater than the threshold. At that point the handler stores one immutable `TokenWarning(total_tokens, threshold)` and invokes its optional receiver outside the lock. Repainting the snapshot does not emit another event. A receiver failure is logged and leaves analysis and the snapshot available.

Read `token_warning_threshold` from run configuration. It defaults to 100000 and can be set with `TRADINGAGENTS_TOKEN_WARNING_THRESHOLD`. An unset or empty setting uses the default. Other values must parse as positive integers, or configuration raises an error naming the setting. The threshold is informational. It does not change the model output limit or checkpoint identity.

The CLI displays the snapshot in the live layout and requests a refresh at the crossing so a short final stage can still show the warning. A terminal without live display support receives one printed warning. The CLI restores temporary message and report logging methods when the run exits.

For FEAT-06, construct a fresh `StatsCallbackHandler(warning_threshold=threshold, on_token_warning=receiver)` per browser analysis. Pass it to the existing model and graph callback paths. The receiver runs on the model-completion thread, so it should enqueue the two values for the current run's activity stream and let the browser layer publish them. The page should read existing counters through `get_stats()` and associate the warning with the current run. Replay TOK-T1 and TOK-T2 through the browser once wired.

We kept the comparison in the callback because it already owns token counts and receives model completion events. Polling the graph stream alone could delay notification during a slow model call. A separate budget controller would duplicate accounting and add an execution policy outside FR-TOK-01.
