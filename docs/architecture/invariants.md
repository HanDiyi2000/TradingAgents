# Invariant register

| ID | Rule | Requirement | Enforcing component | Verification | Operational fallback |
| --- | --- | --- | --- | --- | --- |
| INV-OPT-01 | Every admitted record matches the stock and is verifiably available by the analysis cutoff | INV-OPT-01 | `src/tradingagents/dataflows/options.py`, before model input | OPT-T6, including mixed eligible, wrong-symbol, unknown-time and future records | Drop ineligible records. If none remain, emit the unavailable notice and continue under FR-OPT-05. |

This register contains only invariants approved in the requirements registry. The
FEAT-05 traceability rule discussed during implementation was not approved as a
new invariant and is therefore not promoted into this table.
