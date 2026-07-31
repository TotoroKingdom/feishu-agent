from __future__ import annotations

import re
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._ops import ARTIFACTS, ROOT, run


SUSPICIOUS_PATTERNS = [
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("OpenAI key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("Private key", re.compile(r"-----BEGIN [A-Z0-9 ]+PRIVATE KEY-----")),
]

SKIP_DIRS = {
    ".git",
    ".github",
    ".idea",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".worktrees",
    "__pycache__",
    "node_modules",
}

SKIP_FILES = {
    ".env",
}

TEXT_SUFFIXES = {
    ".css",
    ".csv",
    ".env.example",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".py",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".txt",
    ".tsx",
    ".yml",
    ".yaml",
}


def _iter_text_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name in SKIP_FILES:
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {
            ".env.example",
            "Dockerfile",
        }:
            continue
        files.append(path)
    return files


def main() -> None:
    ARTIFACTS.mkdir(exist_ok=True)
    compose_snapshot = ARTIFACTS / "compose.config.yml"
    with compose_snapshot.open("w", encoding="utf-8", newline="\n") as stream:
        run(["docker", "compose", "config"], ROOT, stdout=stream)

    findings: list[str] = []
    scan_roots = [ROOT, ARTIFACTS]
    for scan_root in scan_roots:
        for path in _iter_text_files(scan_root):
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for label, pattern in SUSPICIOUS_PATTERNS:
                if pattern.search(content):
                    findings.append(f"{label}: {path}")

    if findings:
        raise SystemExit("Secret scan found suspicious values:\n" + "\n".join(findings))


if __name__ == "__main__":
    main()
