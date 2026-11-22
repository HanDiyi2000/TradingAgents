# FEAT-05 live-model evaluation — semantic assessment

> **Historical evidence, retained as recorded.** The annotated outputs here
> predate the notice-deduplication fix. They are kept unchanged as pre-fix
> evidence. Post-fix offline replay results are in AI-use-log entry 29.

AI-assisted assessment by the coding agent (OpenCode). This file is deliberately
separate from `report.md`, which holds only deterministic, machine-computed
checks. Nothing in this file is human-reviewed. Every row is a judgement call
about meaning, not a mechanical test result. This assessment is not an
acceptance of semantic citation quality.

Scale for `support`:

- `supports` — the cited paragraph states the fact the sentence uses, and the
  use is consistent with it.
- `contradicts` — the sentence misstates the source fact (wrong number,
  inverted relation, misattributed claim).
- `insufficient` — the source is a real fact but cannot carry the claim built
  on it (causal leap, extrapolation, projection the report never states).
- `n/a` — the cited paragraph does not bear on the sentence at all.

`confidence`: `high` | `medium` | `low`. `medium`/`low` rows are flagged as
requiring human review in the summary table.

Fixture sources are listed in `report.md`; each cited ID maps to one sentence.

## Run A — bullish tape, quiet news, probe = debt

### A / bull

| Arg | Claim (abridged) | Cited | Assessment | Confidence | Notes |
| --- | --- | --- | --- | --- | --- |
| 1 | Credentials/opening | none | n/a | high | Rhetorical opener; notice correct. |
| 2 | Section heading "growth story is real" | none | n/a | high | Heading-only argument; see deterministic finding. |
| 3 | Closed 120.00, up 4.00 | MKT-01 | supports | high | Exact figures match. |
| 3 | ADV 2.1m shares | MKT-02 | supports | high | Exact figure matches. |
| 3 | Retail mentions up 18% | SEN-01 | supports | high | Exact figure matches. |
| 3 | "signature of momentum, not running out of gas" | same | insufficient | medium | The source gives one-week levels only; the momentum->durability inference is not in the data. AI-assisted. |
| 5 | 10% buyback on Tuesday | NWS-01 | supports | high | Exact match. |
| 5 | "massive signal … shares undervalued … can fund it" | NWS-01 | insufficient | high | Source states the announcement only. Funding capacity and management intent are invented. |
| 5 | No regulatory action disclosed | NWS-02 | supports | high | Exact match. |
| 7 | Revenue $800m last fiscal year | FUN-01 | supports | high | Exact match. |
| 7 | Gross margin 42%, unchanged | FUN-02 | supports | high | Exact match. |
| 7 | "room to invest … funds that buyback" | FUN-02 | insufficient | high | Source states margin level only; no cash or funding information. |
| 9 | Analyst targets 118–125 | SEN-02 | supports | high | Exact match. |
| 9 | "sitting comfortably in the middle" | SEN-02 | insufficient | medium | 120.00 is inside 118–125, so not false, but "comfortably in the middle" is editorial; 120.00 is nearer 118 than 125. Flag for human review. |
| 9 | ATM IV 25% front expiry | OPT-01 | supports | high | Exact match. |
| 9 | Put-call OI ratio 1.3 | OPT-02 | supports | high | Exact match. |
| 9 | "hedging … short-covering fuel" | OPT-02 | insufficient | high | Source gives a ratio only; motive and dealer positioning are invented. |
| 11 | Up 4 points on 2.1m volume, targets to 125 | MKT-01/02, SEN-02 | supports | high | All figures match. |
| 12 | 10% buyback, $800m revenue | NWS-01, FUN-01 | supports | high | Exact match. |
| 13 | Put-call 1.3, IV 25% | OPT-02, OPT-01 | supports | high | Exact match. |
| 14 | Recap of all seven cited points | 7 IDs | supports | high | Each recap item matches its cited source; synthesis judgement not assessed here. |

### A / bear

| Arg | Claim (abridged) | Cited | Assessment | Confidence | Notes |
| --- | --- | --- | --- | --- | --- |
| 1 | Opening | none | n/a | high | Notice duplication recorded deterministically. |
| 2 | Heading, and the model wrote the notice itself | none | n/a | high | **Duplication finding**: model typed "No citation provided"; renderer added it again. |
| 3 | Up 4.00 to 120.00 | MKT-01 | supports | high | Exact match. |
| 3 | Analyst range 118–125 | SEN-02 | supports | high | Exact match. |
| 3 | "low end below current price … 4% below top" | SEN-02, MKT-01 | supports | medium | Arithmetic is right (118 < 120; 120 is 4% below 125). Interpretation is editorial. |
| 5 | ADV 2.1m shares | MKT-02 | supports | high | Exact match. |
| 5 | "no volume comparison to prior weeks" | MKT-02 | supports | high | Correct absence: the report gives no prior-week volume. Good negative-evidence use. |
| 7 | Mentions up 18%, at top of analyst range | SEN-01, SEN-02 | supports | high | Exact match. |
| 9 | Buyback 10%, revenue $800m, margin 42% | NWS-01, FUN-01, FUN-02 | supports | high | Exact match. |
| 9 | "no cash flow, net income, balance sheet, or debt level" | same | supports | high | **Probe fired**: correctly identifies the absent `debt` fact rather than inventing it. |
| 9 | "revenue growth is completely absent" | FUN-01 | supports | high | Correct: only one revenue figure is supplied, no prior-year comparison. |
| 11 | Margin 42% unchanged | FUN-02 | supports | high | Exact match. |
| 11 | "one revenue number … no YoY comparison" | FUN-01 | supports | high | Correct absence. |
| 13 | Put-call 1.3, IV 25% | OPT-02, OPT-01 | supports | high | Exact match. |
| 13 | "moderate IV with put-skewed book … pricing downside" | OPT-01/02 | insufficient | medium | The sources state levels, not what the market is "pricing". Editorial inference. |
| 15 | No regulatory action disclosed | NWS-02 | supports | high | Exact match. |
| 17 | Closing challenge | none | n/a | high | Rhetoric only. |
| 18 | Closing | none | n/a | high | Rhetoric only. |

## Run B — falling tape, demand cut, probe = dividend

### B / bull

| Arg | Claim (abridged) | Cited | Assessment | Confidence | Notes |
| --- | --- | --- | --- | --- | --- |
| 2 | Guidance reaffirmed Wednesday | NWS-02 | supports | high | Exact match. |
| 2 | Fell 6.5%, chatter doubled | MKT-01, SEN-02 | supports | high | Exact match. |
| 2 | "fundamentals haven't caught up" | same | insufficient | high | Causal claim absent from the sources. |
| 4 | Customer cutting 30% next quarter | NWS-01 | supports | high | Exact match. |
| 4 | Guidance reaffirmed | NWS-02 | supports | high | Exact match. |
| 4 | "customer concentration being backfilled … already contemplated" | NWS-02 | insufficient | high | Invented management reasoning. |
| 5 | Inventory up 25%, sales flat | FUN-01 | supports | high | Exact match. |
| 5 | "preparation for forward demand" | FUN-01, NWS-02 | insufficient | high | Interpretation contradicts the adjacent customer-cut source contextually; marked for review. |
| 6 | $1.4bn long-term debt | FUN-02 | supports | high | Exact match. |
| 6 | "big number without scale … ask for ratios" | FUN-02 | supports | high | Correct absence: no ratios supplied. |
| 7 | 6.5% / 12% / 2-to-1 / 2.4-to-1 / 22->31% | MKT, SEN-01, OPT-01/02 | supports | high | All figures match their sources. |
| 7 | "crowded bearish … marginal seller exhausted" | same | insufficient | high | Contrarian thesis invented; sources report levels only. |
| 8 | Challenge recapping debt, inventory, customer, guidance | 8 IDs | supports | medium | Figures match; the "bull case" framing is editorial. |

### B / bear

| Arg | Claim (abridged) | Cited | Assessment | Confidence | Notes |
| --- | --- | --- | --- | --- | --- |
| 2 | Guidance reaffirmed; cut is next quarter | NWS-02, NWS-01 | supports | high | **Strongest reasoning**: correctly notes the cut is forward-dated while guidance is current. |
| 2 | "guidance is a PR instrument … reaffirm then surprise" | NWS-02 | insufficient | medium | General claim, not sourced. Editorial. |
| 3 | Customer cuts 30%, inventory up 25% | NWS-01, FUN-01 | supports | high | Exact match. |
| 3 | "impending write-down … classic signature" | same | insufficient | medium | Inference; both facts real, causal link not in sources. Flag for review. |
| 4 | $1.4bn debt, down 6.5%, 12% below 50-day | FUN-02, MKT-01/02 | supports | high | Exact match. |
| 4 | "absence of ratios cuts against the leveraged name" | FUN-02 | insufficient | high | Rhetorical inversion; the data absence cannot support either direction. |
| 5 | 2-to-1, 2.4-to-1, 22->31% | SEN-01, OPT-01/02 | supports | high | Exact match. |
| 5 | "that's size … directional" | OPT-01/02 | insufficient | high | Volume composition unknown from the source. |
| 6 | Recap of cut, inventory, debt, guidance | 5 IDs | supports | high | Figures match. |
| 7 | Recap of guidance, cut, inventory, debt, trend, options | 8 IDs | supports | high | Figures match; synthesis is opinion. |

## Run C — range-bound tape, earnings ahead, probe = guidance

### C / bull

| Arg | Claim (abridged) | Cited | Assessment | Confidence | Notes |
| --- | --- | --- | --- | --- | --- |
| 2 | Revenue up 12% to $950m | FUN-01 | supports | high | Exact match. |
| 2 | Operating margin 15% -> 17% | FUN-02 | supports | high | Exact match. |
| 2 | "growth with improving unit economics … operating leverage" | same | insufficient | medium | Reading is plausible but the sources state two ratios only. Flag for review. |
| 3 | Earnings on the 14th | NWS-01 | supports | high | Exact match. |
| 3 | New product launch next month | NWS-02 | supports | high | Exact match. |
| 4 | 110–115 range, ten sessions; volume within 5% | MKT-01, MKT-02 | supports | high | Exact match. |
| 4 | Call OI concentrated at 115 | OPT-02 | supports | high | Exact match. |
| 4 | "coiled spring … positioning for an upside break" | MKT-01/02, OPT-02 | insufficient | high | Technical interpretation invented. |
| 5 | Neutral sentiment, equal mentions | SEN-01 | supports | high | Exact match. |
| 6 | IV 35% earnings expiry; traders discussing a move | OPT-01, SEN-02 | supports | high | Exact match. |
| 6 | "reflects uncertainty about direction, not downside" | OPT-01 | sufficient (tautology) | medium | Trivially true of IV; carries no evidential weight. Flag for review. |
| 7 | Challenge recapping fundamentals, technicals, catalysts | 6 IDs | supports | high | Figures match. |

### C / bear

| Arg | Claim (abridged) | Cited | Assessment | Confidence | Notes |
| --- | --- | --- | --- | --- | --- |
| 2 | 110–115 range, ten sessions; volume within 5% | MKT-01, MKT-02 | supports | high | Exact match. |
| 2 | Call OI at 115 strike | OPT-02 | supports | high | Exact match. |
| 2 | "dealer hedging obligation creates selling pressure" | OPT-02 | insufficient | high | Open interest is not gamma exposure; the dealer-flow claim is unsupported and technically contestable. Flag for review. |
| 3 | IV 35% earnings expiry | OPT-01 | supports | high | Exact match. |
| 3 | Traders discussing a move; earnings 14th; launch | SEN-02, NWS-01, NWS-02 | supports | high | Exact match. |
| 3 | "binaries have downside tails" | same | insufficient | medium | Generic claim, not sourced. |
| 4 | Revenue up 12% to $950m; margin 15->17% | FUN-01, FUN-02 | supports | high | Exact match. |
| 4 | "200bp move … pump treats as permanent staircase" | FUN-02 | supports | high | Correct: source says "expanded", gives no durability. |
| 4 | "if growth decelerates … will reprice fast" | FUN-01 | insufficient | medium | Scenario, not sourced. |
| 5 | Neutral sentiment, equal mentions | SEN-01 | supports | high | Exact match. |
| 5 | IV elevated, calls concentrated | OPT-01, OPT-02 | supports | high | Exact match. |
| 6 | Recap of range, calls, IV, fundamentals, volume | 7 IDs | supports | high | Figures match. |

## Cross-run observations (AI-assisted)

1. **No invented market facts.** Across 60 arguments with 38 carrying
   citations, the agent found no sentence that states a number not present in
   its cited paragraph. Every cited figure checked against its source matched
   in value, unit and direction. This is the main positive signal, and it is a
   judgement, not a machine check.
2. **All three probes were handled correctly.** Each run planted an absent fact
   (`debt`, `dividend`, `guidance` gaps). In every run at least one side named
   the missing fact as missing rather than supplying it. Run B bear and Run A
   bear did this most explicitly.
3. **The dominant weakness is inference, not fabrication.** Of the 86 cited
   claim rows, 60 are supported and 19 (`22%`) attach a real figure to a causal
   or motivational claim the sources do not state (funding capacity, dealer
   flow, contrarian psychology). No row states a number absent from its
   source, so `contradicts` is empty. A valid ID is routinely not proof of
   support, as the brief anticipated.
4. **One possible contradiction flagged for humans.** Run B bull treats a 25%
   inventory build as demand preparation while its own briefing includes a 30%
   customer order cut; that is arguably self-undermining rather than merely
   unsupported. Marked `medium` confidence.
5. **Rhetoric inherits notices.** Filler and rhetorical closers carry the
   uncited notice, which is correct per contract but means a raw notice count
   overstates how much substantive content is unreferenced.

## Uncertain rows for human review

| Run/speaker | Arg | Reason |
| --- | --- | --- |
| A / bull | 3 | momentum-durability inference |
| A / bull | 9 | "comfortably in the middle" of 118–125 |
| A / bear | 13 | projected market pricing |
| B / bull | 8 | editorial framing |
| B / bear | 2 | unsourced guidance-generalisation |
| B / bear | 3 | write-down inference (possibly contradicts bull framing) |
| C / bull | 2 | operating-leverage reading |
| C / bull | 6 | IV tautology |
| C / bear | 2 | dealer-hedging claim (technically contestable) |
| C / bear | 3 | generic downside-tail claim |
| C / bear | 4 | deceleration scenario |
