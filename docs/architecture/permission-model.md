# Permission model

| Role | Read allowlist | Write allowlist | Guard and enforcement |
| --- | --- | --- | --- |
| Plan | AGENTS.md, Prompt.md, the two requirement YAMLs, registry schema, root blueprint, architecture and governance Markdown; tracked source and tests named in the feature plan | None | Read-only investigation. Return the proposed concrete edit set and dependencies to the human. |
| Build | Plan inputs and the approved test files and implementation paths | Only the implementation paths explicitly released in the approved plan | Approved tests, requirements, review verdicts, permissions and human rules are frozen. On an unlisted dependency, return to planning. |
| Test author | Requirement, fit criterion, interface contract, applicable ADR and test fixtures | Only named test files before test approval | Submit the diff for human review. After approval retain the exact test version; move a changed expectation back through approval. |
| Verify | Approved tests and fixtures, source under review, ADR, trace matrix, CI output | None | Report failures and distinguish environment failures from assertion failures. A reviewer records the verdict. |

A directory name in a feature plan does not authorize its unseen contents. Enumerate paths relative to the repository, bind them to the role and deny all other paths. Never issue credentials, provider sign-in material or unrestricted shell access to these roles. Runtime agents such as Bull Researcher have no development-file rights by virtue of their application role.

### Enforced configuration

The project pins the permission syntax to OpenCode 1.18.32. The JSONC file enumerates concrete repository-relative resources. The project entry configuration exposes the same roles and rules to a normal OpenCode launch and retains the CityU provider with environment-variable references. Plan is the initial role. Build and Test author prompt before each eligible edit; the supervising student checks that path against the approved plan. Verify has read access only. Shell, remote tools and unlisted paths are denied. A human maintainer must explicitly extend the allowlist before a new file can be edited. Compare the four roles in `opencode debug config --pure` against the JSONC after changing either file.
