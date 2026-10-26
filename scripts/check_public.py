"""Check the Git index before publishing. Never prints suspected secret contents."""

import re
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
paths = (
    subprocess.check_output(
        ["git", "-c", f"safe.directory={root.as_posix()}", "ls-files", "-z"], cwd=root
    )
    .decode()
    .split("\0")
)
failures = []
patterns = [
    rb"AIza[0-9A-Za-z_-]{30,}",
    rb"sk-[A-Za-z0-9_-]{20,}",
    rb"gh[pousr]_[A-Za-z0-9]{20,}",
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    rb"mongodb(?:\+srv)?://[^\s:/]+:[^\s@]+@",
]
for relative in filter(None, paths):
    p = Path(relative)
    if (
        (p.name.startswith(".env") and p.name != ".env.example")
        or p.name in {"credentials.json", "token.json"}
        or p.suffix in {".pem", ".key"}
        or any(
            part in {"storage", "node_modules", ".venv", "__pycache__"}
            for part in p.parts
        )
    ):
        failures.append((relative, "private/runtime artifact"))
    if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
        continue
    data = (root / p).read_bytes()
    if any(re.search(pattern, data) for pattern in patterns):
        failures.append((relative, "possible credential pattern"))
if failures:
    for filename, reason in failures:
        print(f"FAIL: {filename}: {reason}")
    raise SystemExit(1)
print(
    f"Public-source index check passed ({len(list(filter(None, paths)))} files). This is a pattern check, not a guarantee."
)
