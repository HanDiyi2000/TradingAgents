# Architecture risks

| Assumption at risk | Failure signal | Response and ownership |
| --- | --- | --- |
| Vendor timestamps establish eligibility | A snapshot has no attributable instrument or availability time | The data adapter drops the observation before model input; verify INV-OPT-01. |
| A valid source ID supports the claim | Semantic assessment finds a real paragraph cited for a different assertion | The reviewer checks the actual claim and source; retain model text and ID independently. |
| A structured judgement detects repetition | The fixed judge set reports a false NO_PROGRESS | Keep the failure visible and reopen prompt evaluation; malformed judgements follow UNKNOWN. |
| Report identity survives preview rendering | More than one DOM element has the source target ID | Check navigation against the analyst section and saved artifact independently. |
| The quick-tier context fits the model | Input growth approaches the provider limit | Revisit the ADR 001 budget and compaction design before changing the runtime policy. |
