# Technical debt register

| Category | Evidence | Impact | Owner | Next review |
| --- | --- | --- | --- | --- |
| Evaluation debt | FEAT-02's three live CityU DeepSeek semantic-evaluation runs all failed or returned a structured-output miss; the exact outcomes are retained in `docs/architecture/trace-matrix.md`. | Offline routing is verified, but real-model classification of new evidence and first replies is not accepted as reliable. | Unassigned | Before changing the debate judge, its model or its semantic fixtures |
| Evaluation debt | The FEAT-05 live sample resolved 139/139 IDs, but the unreviewed semantic assessment classified 60/86 cited claim rows as supported, 19 as insufficient and 7 as evidential-free or tautological; 11 rows are marked for human review in `docs/evaluations/feat05-live/semantic-assessment.md`. | A syntactically valid citation does not prove that the paragraph supports the claim. | Unassigned | Human review of the labelled rows, then before any citation-quality acceptance claim |
| Prompt rot | ADR 001 and the architecture blueprint record no approved project-wide prompt token cap, compaction threshold or critical-constraint reinjection policy. | Long analyst reports and histories may grow until a provider limit or ad-hoc truncation is encountered. | Unassigned | Before the next prompt/model change or before submission if the team adopts a common context budget |
| Guardrail debt | `docs/architecture/permission-model.md`, `docs/code-governance/mcp-tool-manifest.md` and `.opencode/permissions.jsonc` now define named tool and path allowlists; independent human sign-off and negative checks remain outstanding. | A resolved configuration proves loading; attempted reads and edits under each role still require independent verification. | Unassigned | Before claiming D2.6/D3 permission compliance or enabling unattended tool use |
| Human/cognitive debt | Several local review rows still have no PR identifier, final reviewer verdict or remote-CI result. | Local evidence is available, but merge readiness and final accountability are not established for every feature. | Unassigned | At PR creation and final submission review |

## Additional categories examined

| Category | Concrete exposure | How the team can detect or retire it |
| --- | --- | --- |
| Hallucinated dependencies | New model adapters can refer to an SDK absent from a clean installation. | Check declared extras and reproduce the clean-install import job before accepting a new adapter. |
| Untouchable code | The bull/bear state contract spans resume, routing and rendering. A change to one consumer can break an older checkpoint. | Retain the old-state and real-resume fixtures when changing debate state. |
| Hidden dependencies | The live judge depends on provider credentials and structured-output support. The offline judge fixture supplies both implicitly. | Report transport failure, parse failure and semantic disagreement separately. |
| Agent-induced bloat | Independent CLI/web event interpretation would create two owners for ordering and status. | Keep both on the shared stream interpreter; check the public CLI and HTTP entry points when the event shape changes. |
