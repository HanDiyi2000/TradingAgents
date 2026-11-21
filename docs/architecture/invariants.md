# Invariant register

| ID | Rule | Requirement | Enforcing component | Verification | Operational fallback |
| --- | --- | --- | --- | --- | --- |
| INV-OPT-01 | Every admitted record matches the stock and is verifiably available by the analysis cutoff | INV-OPT-01 | Proposed options data adapter, before model input | OPT-T6, including mixed eligible and future records | Drop ineligible records. If none remain, emit the unavailable notice and continue under FR-OPT-05. |
