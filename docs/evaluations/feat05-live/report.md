# FEAT-05 live-model evaluation

> **Historical evidence, retained as recorded.** The annotated outputs here
> predate the notice-deduplication fix. They are kept unchanged as pre-fix
> evidence. Post-fix offline replay results are in AI-use-log entry 29.

- Date: 2026-11-23
- Model: `CS5351/DeepSeek-V4-Flash` (configured `modelID` in `opencode.json`)
- Endpoint host: `llm.cs.cityu.edu.hk` (path `/v1`)
- Settings: `temperature=0`, `max_tokens=1400`, 3 runs x (1 bull turn + 1 bear turn)
- Code exercised: the real `create_bull_researcher` / `create_bear_researcher`
  nodes and `tradingagents.agents.citations` (`build_report_paragraphs`,
  `split_arguments`, `resolve_turn`, `render_annotated_turn`).
- No market data was fetched and no full stock analysis was run. All input is
  the fixed fixtures below.
- Credentials were read from the configured `.opencode/cityu/.env` file at run
  time and never printed, logged or committed. Token usage is the provider's
  reported `usage` object; no cost is estimated.

Artifacts in this directory:

| File | Contents |
| --- | --- |
| `results.json` | Fixtures, paragraph maps, raw responses, annotated output, per-turn argument records, token usage, finish reasons. |
| `prompt-{A,B,C}-{bull,bear}.txt` | Exact prompts the researcher nodes sent. |
| `report.md` | This file: deterministic checks and counts only. |
| `semantic-assessment.md` | AI-assisted semantic judgement per argument, kept separate. |
| `../../scripts/eval_feat05_live.py` | The harness that produced the artifacts. |

## Method

Each run supplies five short analyst reports (market, sentiment, news,
fundamentals, options), two sentences each. `build_report_paragraphs` assigns
the stable IDs `MKT-01/02, SEN-01/02, NWS-01/02, FUN-01/02, OPT-01/02`. The
prompts contain these IDs and the pinned label instruction. Each run plants one
fact that is *absent* from its reports, as a probe for invention:

| Run | Tape | Absent probe |
| --- | --- | --- |
| A | Strong day, quiet news | `debt` |
| B | Falling tape, customer order cut | `dividend` |
| C | Range-bound, earnings due | `guidance` beyond the dated release |

### Fixture sources

- A: `MKT-01` closed 120.00, up 4.00 · `MKT-02` ADV 2.1m · `SEN-01` retail
  mentions +18% · `SEN-02` targets 118–125 · `NWS-01` 10% buyback Tuesday ·
  `NWS-02` no regulatory action · `FUN-01` revenue $800m · `FUN-02` gross
  margin 42% unchanged · `OPT-01` ATM IV 25% · `OPT-02` put-call OI 1.3.
- B: 6.5% fall over five sessions · 12% below 50-day · bearish mentions 2:1 ·
  chatter doubled · customer cuts orders 30% · guidance reaffirmed Wednesday ·
  inventory +25% with flat sales · $1.4bn long-term debt · put volume 2.4:1 ·
  IV 22->31%.
- C: 110–115 range for ten sessions · volume within 5% · sentiment neutral ·
  earnings on the 14th · product launch next month · revenue +12% to $950m ·
  operating margin 15->17% · earnings-expiry IV 35% · calls concentrated at 115.

## Deterministic results

These are machine-computed and reproducible from `results.json`. They say
nothing about whether a claim is *true*, only about labels, notices, numbering
and rendering.

| Run / speaker | Arguments | With >=1 ID | IDs used | IDs not in map | Extra notices on render | Heading-only args | Tokens (p/c) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A / bull | 14 | 8 | 24 | 0 | 6 | 5 | 553 / 950 |
| A / bear | 18 | 7 | 13 | 0 | 11 | 0 | 2530 / 1369 |
| B / bull | 8 | 6 | 24 | 0 | 2 | 1 | 549 / 881 |
| B / bear | 7 | 6 | 39 | 0 | 1 | 0 | 2338 / 1221 |
| C / bull | 7 | 6 | 17 | 0 | 1 | 0 | 544 / 752 |
| C / bear | 6 | 5 | 22 | 0 | 1 | 0 | 2065 / 1031 |
| **Total** | **60** | **38** | **139** | **0** | **22** | **6** | **8579 / 6204** |

Total tokens 14783 (provider-reported). All six turns finished with
`finish_reason=stop`.

### Headline counts

- IDs inside the map: **139 / 139** (100%). No invalid-ID notice was produced.
- Arguments carrying at least one ID: **38 / 60** (63%). The 22 without an ID
  are openers, headings, sub-headings and rhetorical closers.
- Uncited-notice correctness on first pass: **60 / 60** (100%) — every argument
  without an ID got exactly one `No citation provided`, and no argument with
  valid IDs got one, in the stored records.
- **Duplicate notices in rendered output: 22 / 60 arguments (37%)** — see
  failure F1.

### An early, discarded measurement

The first attempt used `max_tokens=500`. All six turns hit
`finish_reason=length` mid-sentence, so those responses were discarded and the
evaluation re-run at `max_tokens=1400`. Only the finished responses are
analysed. The truncated run is not part of these counts.

## Deterministic failures

### F1 — renderer duplicates a notice the model wrote itself

`resolve_turn` assigns `note = UNCITED` to any argument with no citations
without checking whether the speaker's text already contains the phrase. Run A
bear wrote `— *No citation provided.*` into its own sub-headings; the renderer
then appended the notice again:

```
**First, the "momentum" story is a one-day move, not a trend.** — *No citation provided.* — *No citation provided.*
```

Observed in 22 of 60 arguments, exactly matching the 22 uncited arguments. It
appeared in one run (A bear) for 11 arguments, but the trigger is general: any
model that echoes the notice phrase will be double-noticed. This is a
render-side defect, not a citation-resolution defect — the stored records
(`resolve_turn` output) are correct.

### F2 — heading-only arguments receive an uncited notice

Six arguments (5 in A bull, 1 in B bull) are a single bold line, e.g.
`**The growth story is real, and the market is starting to price it in.**`.
The debate renderer includes them as arguments and marks them
`No citation provided`. Contracted behaviour for the report exporter excludes
headings; the debate path does not. This makes the uncited rate look worse than
the substantive content warrants. Whether this is intended for the debate
path needs a human decision; the approved tests do not cover a model that
emits bold headings in a debate turn.

### Passing checks worth recording

- Re-rendering the stored records produced no additional or changed notices
  beyond F1's duplication, i.e. rendering is idempotent with respect to its own
  input.
- Each speaker numbered its own turns correctly (bull and bear both start at
  turn 1).
- Every prompt contained all ten paragraph IDs and no literal `[FUN-01]`
  example, per the approved contract.

## Not claimed

- Live-model citation **quality** is not verified. It is assessed by the agent
  in `semantic-assessment.md`, which is AI-assisted and unreviewed.
- No cost is reported; only provider-reported token counts are given.

## Summary for review

| Measure | Result |
| --- | --- |
| Runs / turns | 3 / 6 (all complete) |
| Arguments analysed | 60 |
| Cited IDs valid | 139 / 139 |
| Argument rendered with a duplicate notice | 22 / 60 (F1) |
| Heading-only arguments flagged uncited | 6 / 60 (F2) |
| Probes where absent fact was invented | 0 / 3 |
| Cited claim rows judged supported by their cited source | 60 / 86 (70%) |
| Cited claim rows marked `insufficient` (source real, claim overreaches) | 19 / 86 (22%) |
| Claim rows marked `contradicts` | 0 / 86 |
| Claim rows judged without an evidential claim (`n/a`) or tautological | 7 / 86 |
| Rows flagged for human review | 11 |

Production code and the approved tests were left unchanged. Nothing was
committed or pushed. This evaluation does not constitute human approval or
live-quality acceptance.
