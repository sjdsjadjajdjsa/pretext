"""Capture model outputs into the regression corpus.

Usage: uv run python scripts/capture_corpus.py MODEL [MODEL ...]

Needs a configured endpoint and key (see README). The corpus is checked in so the
suite stays offline; re-run this after a prompt change and read the diff.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pretext import Client, resolve_settings
from pretext.models import load_profile

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "tests" / "fixtures" / "corpus"
PROFILE = ROOT / "tests" / "fixtures" / "profiles" / "helpdesk.yaml"


def main(models: list[str]) -> int:
    if not models:
        print("usage: capture_corpus.py MODEL [MODEL ...]", file=sys.stderr)
        return 2

    CORPUS.mkdir(parents=True, exist_ok=True)
    profile = load_profile(PROFILE)

    for model in models:
        settings = resolve_settings(model=model, max_tokens=12000)
        simulation = Client(settings).generate(profile)
        target = CORPUS / f"{model.replace('/', '__')}.json"
        target.write_text(
            json.dumps(
                {
                    "model": model,
                    "profile": profile.model_dump(mode="json"),
                    "simulation": simulation.model_dump(mode="json"),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"wrote {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
