from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "changelog_section.py"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, check=False
    )


def test_extracts_section():
    result = run("0.2.0")
    assert result.returncode == 0
    assert "--from-file" in result.stdout
    assert "## 0.1.0" not in result.stdout


def test_missing_section():
    result = run("9.9.9")
    assert result.returncode == 1
    assert "no changelog section" in result.stderr


def test_missing_argument():
    assert run().returncode == 1
