# Project covenant

## Abstractions and dependencies

Extend the existing owning module when it can satisfy the requirement. Do not add a parallel workflow, duplicate module, or new abstraction for behavior already owned by an existing component. Propose a new abstraction only when the feature plan explains its responsibility, why existing modules are insufficient, and how it fits the architecture.

Reuse existing dependencies where they meet the requirement. Any new dependency must be justified in the human-approved plan, including its purpose and effect on verification. Preserve the dependency direction and module ownership defined in `docs/code-governance/structural-constraints.md`.

## Tests and safety

Define test expectations from the approved requirements and interface contracts, independently of the implementation. Include at least one negative test for each feature.

A safety-critical code change requires an architecture decision record (ADR) and explicit human approval before implementation.

## Context freshness

When a requirement changes, review the affected project rules and update them within one sprint. Keep those changes subject to the same human review and file permissions as other governance changes.
