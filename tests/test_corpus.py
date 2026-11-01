"""Invariants over saved model outputs.

The corpus is captured by `scripts/capture_corpus.py`. It is not a golden snapshot:
prose may change, but the structural promises of the prompt must hold.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import pytest

from pretext.models import Profile, Simulation

CORPUS = Path(__file__).parent / "fixtures" / "corpus"
FILES = sorted(CORPUS.glob("*.json"))


def test_corpus_exists():
    assert len(FILES) >= 2


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_entry_is_valid(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    profile = Profile.model_validate(data["profile"])
    simulation = Simulation.model_validate(data["simulation"])
    assert profile.name and simulation.pretext


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_channels_are_varied(path):
    sim = Simulation.model_validate(json.loads(path.read_text(encoding="utf-8"))["simulation"])
    channels = [step.channel for step in sim.escalation_path]
    assert len(set(channels)) >= 3
    assert all(a != b for a, b in itertools.pairwise(channels))


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_every_stage_hands_over_an_artifact(path):
    sim = Simulation.model_validate(json.loads(path.read_text(encoding="utf-8"))["simulation"])
    assert all(step.artifact for step in sim.escalation_path)


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_opening_is_written_not_described(path):
    sim = Simulation.model_validate(json.loads(path.read_text(encoding="utf-8"))["simulation"])
    opening = sim.opening_message
    assert not opening.lower().startswith(("subject:", "from:"))
    assert "sent from" not in opening.lower()[:120]
    assert len(opening.split()) >= 12


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_pretext_has_substance(path):
    sim = Simulation.model_validate(json.loads(path.read_text(encoding="utf-8"))["simulation"])
    assert len(sim.pretext.split()) >= 100
    assert len(sim.red_flags) >= 2
    assert all(flag.defender_action for flag in sim.red_flags)
