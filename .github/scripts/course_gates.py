"""D7 change-control checks. Run with read-only PR metadata and full git history."""
import json
import os
import subprocess
import sys
from pathlib import Path


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True)


def implementation(path: str) -> bool:
    return path.startswith(("src/", "prompts/", ".github/scripts/", ".github/workflows/")) or path in {
        "main.py", "pyproject.toml", "opencode.json", ".opencode/permissions.jsonc",
    }


def safety(path: str) -> bool:
    return path.startswith(("src/", "prompts/", ".opencode/", ".agent/", ".github/")) or path == "opencode.json"


def inspect_change(history: list, approved: set, head: str) -> list[str]:
    changed = {p for _, paths in history for p in paths}
    first = next((i for i, (_, paths) in enumerate(history) if any(map(implementation, paths))), None)
    errors = []
    if first is not None:
        if "docs/ai-use-log.yaml" not in changed:
            errors.append("Update the AI-use log for code or prompt changes.")
        test_revisions = [i for i, (_, paths) in enumerate(history)
                          if any(p.startswith("test/") for p in paths)]
        if not any(i < first and history[i][0] in approved for i in test_revisions):
            errors.append("Tests need independent approval before implementation.")
        if any(i >= first for i in test_revisions):
            errors.append("The approved tests changed during or after implementation; split a new revision round.")
    if any(map(safety, changed)):
        if not any(p.startswith("docs/architecture/adr/") and p.endswith(".md") for p in changed):
            errors.append("Safety paths require an accompanying ADR.")
        if head not in approved:
            errors.append("Safety paths need independent human review of the candidate head.")
    return errors


def main() -> None:
    pr = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())["pull_request"]
    head = pr["head"]["sha"]
    base = git("merge-base", pr["base"]["sha"], head).strip()
    commits = git("rev-list", "--reverse", "--first-parent", f"{base}..{head}").splitlines()
    history = [(sha, git("diff", "--no-renames", "--name-only", sha + "^1", sha).splitlines())
               for sha in commits]
    repo = os.environ["GITHUB_REPOSITORY"]
    pages = json.loads(subprocess.check_output([
        "gh", "api", "--paginate", "--slurp", f"repos/{repo}/pulls/{pr['number']}/reviews",
    ], text=True))
    # A later dismissal or request for changes revokes the same reviewer's approval.
    reviews: dict[tuple[str, str], str] = {}
    for page in pages:
        for review in page:
            user = review["user"]
            if (user["type"] == "User" and user["login"] != pr["user"]["login"]
                    and review["author_association"] in {"OWNER", "MEMBER", "COLLABORATOR"}
                    and review["state"] in {"APPROVED", "DISMISSED", "CHANGES_REQUESTED"}):
                reviews[user["login"], review["commit_id"]] = review["state"]
    approved = {sha for (_, sha), state in reviews.items() if state == "APPROVED"}
    # Approval must predate the first implementation commit, not just refer to an older diff.
    first = next((sha for sha, paths in history if any(map(implementation, paths))), None)
    if first:
        from datetime import datetime
        cutoff = datetime.fromisoformat(git("show", "-s", "--format=%cI", first).strip())
        early = {r["commit_id"] for page in pages for r in page
                 if r["state"] == "APPROVED" and r["submitted_at"]
                 and reviews.get((r["user"]["login"], r["commit_id"])) == "APPROVED"
                 and datetime.fromisoformat(r["submitted_at"].replace("Z", "+00:00")) < cutoff}
        approved = (approved & early) | (approved & {head})
    errors = inspect_change(history, approved, head)
    net = set(git("diff", "--no-renames", "--name-only", "--diff-filter=AM", base, head).splitlines())
    paths = set(git("diff", "--no-renames", "--name-only", base, head).splitlines())
    if any(map(implementation, paths)) and "docs/ai-use-log.yaml" not in net:
        errors.append("The final PR tree must retain its AI-use log update.")
    if any(map(safety, paths)) and not any(
        p.startswith("docs/architecture/adr/") and p.endswith(".md") for p in net
    ):
        errors.append("The final PR tree must retain its ADR.")
    if paths and "docs/review-memo.md" not in net:
        errors.append("Attach the PR review memo and its verdict before merge.")
    if paths and "docs/review-memo.md" in net:
        memo = git("show", f"{head}:docs/review-memo.md").rstrip()
        last = memo.splitlines()[-1].strip("* .").upper() if memo else ""
        if last != "APPROVE":
            errors.append("The final PR review memo must end with the human APPROVE verdict.")
    if errors:
        sys.exit("\n".join(errors))


if __name__ == "__main__":
    main()
