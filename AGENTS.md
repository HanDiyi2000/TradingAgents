# CS5351 coding-agent entry point

The baseline is TradingAgents 0.7.1, team commit `4cff72b`. Preserve its public imports, CLI, data formats and graph behavior when extending it.

Read `Prompt.md`, `docs/req/prd.yaml`, `docs/req/requirements.yaml`, `architecture-blueprint.md`, then the relevant ADR, invariant register, trace matrix, permission model and verification constraints. Keep the human-authored rules in `.opencode/rules.md` under human control.

For each feature, the human-approved plan must name the editable paths, frozen paths, affected interfaces and verification evidence. The runtime configuration sets a maximum role allowlist. A named path still requires release in the human-approved feature plan. Work in the canonical packages under `src/`. Run the previous offline suite for every round and record results and human interventions.

Read `docs/code-governance/structural-constraints.md` for the component-to-module table and shared interfaces. Read `docs/architecture/permission-model.md` and `docs/code-governance/mcp-tool-manifest.md` for the role boundary before requesting tools. The default for a path outside the allowlist is no read and no write. Requirements, ADR approvals, review verdicts and the human-only rules cannot be altered to turn a failed verification into a pass.
