from __future__ import annotations

import json
from pathlib import Path

import pytest

from pretext import render
from pretext.models import Profile, Simulation

FIXTURE = Path(__file__).parent / "fixtures" / "responses" / "dana.json"


@pytest.fixture
def pair() -> tuple[Profile, Simulation]:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return Profile.model_validate(data["profile"]), Simulation.model_validate(data["simulation"])


def test_markdown_has_every_section(pair):
    profile, simulation = pair
    body = render.to_markdown(simulation, profile)
    for heading in (
        "## Pretext narrative",
        "## Opening message",
        "## Escalation path",
        "## Red flags for defenders",
    ):
        assert heading in body
    assert body.count(render.DISCLAIMER) == 1
    assert body.endswith("\n")


def test_markdown_keeps_stage_order(pair):
    profile, simulation = pair
    body = render.to_markdown(simulation, profile)
    positions = [body.index(f"\n{step.stage}. **") for step in simulation.escalation_path]
    assert positions == sorted(positions)


def test_json_round_trips(pair):
    profile, simulation = pair
    body = json.loads(render.to_json(simulation, profile))
    assert Simulation.model_validate(body["simulation"]) == simulation
    assert body["profile"]["name"] == profile.name
    assert body["disclaimer"] == render.DISCLAIMER


def test_json_omits_headers_from_opening(pair):
    _, simulation = pair
    assert not simulation.opening_message.lower().startswith("subject:")


def test_rich_render_includes_defender_actions(pair):
    profile, simulation = pair
    out = render.console(no_color=True, width=100)
    with out.capture() as captured:
        render.render_simulation(simulation, profile, out)
    text = captured.get()
    assert "Defender action:" in text
    assert render.DISCLAIMER in " ".join(text.split())


def test_difficulty_bar(pair):
    profile, simulation = pair
    out = render.console(no_color=True, width=100)
    with out.capture() as captured:
        render.render_simulation(simulation, profile, out)
    assert f"{simulation.difficulty}/5" in captured.get()


def test_narrow_terminal_does_not_crash(pair):
    profile, simulation = pair
    out = render.console(no_color=True, width=40)
    with out.capture() as captured:
        render.render_simulation(simulation, profile, out)
    assert simulation.escalation_path[0].action.split()[0] in captured.get()
