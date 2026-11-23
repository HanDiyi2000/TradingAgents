"""Check the whole source tree; allow only diagnostics already present on the base."""
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path


def diagnostics(root: Path) -> Counter:
    cmd = [sys.executable, "-m", "mypy", "--no-incremental", "--ignore-missing-imports",
           "--follow-imports=skip", "--check-untyped-defs", "--no-error-summary",
           "--explicit-package-bases", "--no-pretty", "--no-color-output", "src"]
    result = subprocess.run(cmd, cwd=root, text=True, capture_output=True)
    if result.returncode not in (0, 1):
        sys.exit(result.stderr or result.stdout)
    errors = Counter(re.sub(r":\d+(?::\d+)?: error:", ": error:", line)
                     for line in result.stdout.splitlines() if ": error:" in line)
    if result.returncode and not errors:
        sys.exit(result.stderr or result.stdout or "Type checker failed.")
    return errors


base = sys.argv[1]
with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / "base"
    subprocess.run(["git", "worktree", "add", "--detach", "--quiet", str(path), base], check=True)
    try:
        prior = diagnostics(path) if (path / "src").is_dir() else Counter()
        new = diagnostics(Path.cwd()) - prior
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(path)], check=True)
if new:
    sys.exit("\n".join(new.elements()))
