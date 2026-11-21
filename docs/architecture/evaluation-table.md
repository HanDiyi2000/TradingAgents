# Architecture candidate evaluation

| Candidate | Driver or criterion | Evidence | Tradeoff | Decision |
| --- | --- | --- | --- | --- |
| Separate parallel analyst | Independent selection, report and delivery | Existing analyst registration and shared report writer provide extension points | Extra lookup, model work and downstream context | Selected for Feature 1 |
| Extend Market Analyst | Share existing node and report | Options output would depend on market selection and share its report identity | Fewer nodes, weaker separation of evidence | Rejected for Feature 1 |
