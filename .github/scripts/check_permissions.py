"""D2/D3: check that OpenCode loads the submitted least-privilege role policy."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
policy = json.loads((root / ".opencode/permissions.jsonc").read_text())
entry = json.loads((root / "opencode.json").read_text())
assert all(entry.get(k) == v for k, v in policy.items()), "OpenCode entry and course policy differ"
assert policy["permission"]["*"] == "deny" and entry["default_agent"] == "plan"
assert set(entry["agent"]) == {"plan", "build", "test-author", "verify"}
for role, spec in entry["agent"].items():
    rules = spec["permission"]
    assert set(rules) == {"*", "read", "edit"} and rules["*"] == "deny"
    for action in ("read", "edit"):
        paths = rules[action]
        assert next(iter(paths)) == "*" and paths["*"] == "deny"
        for relative, effect in list(paths.items())[1:]:
            target = (root / relative).resolve()
            assert target.is_relative_to(root) and target.is_file(), relative
            assert not any(c in relative for c in "*?[]"), relative
            assert not any(p.startswith(".env") or p == ".git" for p in Path(relative).parts)
            if action == "edit":
                prefix = {"build": "src/", "test-author": "test/"}.get(role)
                assert prefix and relative.startswith(prefix) and effect == "ask", relative
            else:
                assert effect == "allow"
