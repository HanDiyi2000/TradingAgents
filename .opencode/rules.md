# Always-on rules for coding agents

These rules apply to every Plan, Build, Test author, and Verify session in this
repository. This file is maintained by a human. An agent may edit it only when
the human maintainer explicitly approves that exact change; it must never
change these rules or their permissions to make a feature check pass.

## Start from the approved contract

1. Read `AGENTS.md`, `Prompt.md`, `docs/req/prd.yaml`,
   `docs/req/requirements.yaml`, and `architecture-blueprint.md` in that order.
   Then read the applicable ADR, invariant register, trace matrix, permission
   model, structural constraints, tool manifest, and verification constraints.
   Use the requirements registry for IDs and fit criteria; do not invent an
   approved requirement, invariant, ADR, or test result.
2. Before implementation, present a feature plan that names requirement IDs,
   exact repository-relative paths to edit and paths to freeze, owning modules,
   affected public and cross-module interfaces, test cases, verification commands,
   expected evidence, and ordered steps. Get explicit human approval of the plan
   and proposed tests before implementation. A previous approval does not cover
   additional paths, changed expectations, or a new feature.
3. Treat `.opencode/permissions.jsonc` and the project runtime configuration as
   the maximum role allowlist. The approved plan must also release each exact
   path for the assigned role. A directory name, read permission, or availability
   in a tool does not grant write permission. Deny reads, writes, and tools not
   granted to the role; return an unlisted dependency to planning and the human
   maintainer. Do not use a different tool or role to bypass a denial.

## Respect role and architecture boundaries

4. Plan investigates allowed inputs and proposes changes without writing. Test
   author writes only named, pre-approval test files and submits their exact
   version for human review. Build edits only implementation paths released in
   the approved plan; approved tests remain frozen. Verify reads permitted
   evidence and reports a result without editing. Follow the role-specific
   rights in `docs/architecture/permission-model.md` and the allowed tools in
   `docs/code-governance/mcp-tool-manifest.md`. Shell, remote tools, network
   searches, Git push, and hosted settings are not automatically available to
   coding roles.
5. Extend the TradingAgents 0.7.1 baseline at team commit `4cff72b` in the
   canonical packages under `src/`. Preserve public imports, CLI commands,
   saved data formats, existing graph behavior, and compatibility with older
   state unless an approved architecture decision and migration authorize a
   change. Assign each architectural element to its existing owning module and
   honor the dependency and interface contracts in
   `docs/code-governance/structural-constraints.md`.
6. Treat model output as advisory. Deterministic owners enforce evidence
   eligibility and cutoffs, routing and round caps, citation validity,
   persistence, paths, and rendering. Never let model text grant itself authority
   or select a filesystem effect. If a safety-critical authority boundary,
   graph shape, public interface, or persistence contract must change, return
   to architecture review; safety-critical changes require an ADR and explicit
   human approval.

## Test, report, and hand back

7. Tie each test to a requirement or registered invariant and keep its expected
   outcome independent of the implementation. Include a negative case for each
   feature and a violation case for each applicable invariant; include legacy
   or resume coverage when state changes. Do not weaken an approved test or
   revise a requirement to match a failing implementation. Send conflicts back
   for a human decision and renewed test approval.
8. For every implementation round, present the diff for human review and run
   the previous offline suite along with targeted tests and applicable
   structural, schema, static, contract, security, permission, and behavioral
   gates in `docs/code-governance/verification-constraints.md`. Keep live tests
   and provider-dependent semantic evaluations distinct from offline evidence.
   Record commands, revision, environment, results, failures, skips, and human
   interventions. Never label an unrun, unavailable, or failing check as passed.
9. Hand verification evidence to the human reviewer for the verdict. Do not
   author or rewrite human approvals, review verdicts, requirements, ADR
   approvals, or these human-only rules to turn a failure into a pass. Preserve
   the raw agent session for human annotation. Follow the AI-use log gate for
   code or prompt changes; assess documentation-only changes separately. Never
   record a log entry as if a human intervention or verification occurred when
   it did not.
