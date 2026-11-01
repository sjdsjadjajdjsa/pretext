"""Print the CHANGELOG section for a version, for release notes.

Usage: python scripts/changelog_section.py 0.3.0
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main(version: str) -> int:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    pattern = re.compile(rf"^## {re.escape(version)}\n(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL)
    match = pattern.search(text)
    if not match or not match.group(1).strip():
        print(f"no changelog section for {version}", file=sys.stderr)
        return 1
    print(match.group(1).strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else ""))
