"""Invariants of the prompt, checked against the fixture profiles."""

from __future__ import annotations

from pathlib import Path

import pytest

from pretext.models import Profile, load_profile
from pretext.prompt import SYSTEM_PROMPT, build_payload_messages

FIXTURES = Path(__file__).parent / "fixtures" / "profiles"
PROFILES = sorted(FIXTURES.glob("*.yaml"))


def test_fixtures_exist():
    assert len(PROFILES) >= 4


@pytest.mark.parametrize("path", PROFILES, ids=lambda p: p.stem)
def test_fixture_profiles_load(path):
    assert load_profile(path).company


@pytest.mark.parametrize("path", PROFILES, ids=lambda p: p.stem)
def test_user_prompt_carries_profile(path):
    profile = load_profile(path)
    content = build_payload_messages(profile)[1]["content"]
    assert profile.name in content
    assert profile.company in content
    assert profile.communication_style in content
    assert content.rstrip().endswith("Return only the JSON object.")


def test_system_prompt_states_core_rules():
    assert "The persona is the target" in SYSTEM_PROMPT
    assert "never the same channel twice in a row" in SYSTEM_PROMPT
    assert "fictional" in SYSTEM_PROMPT.lower()


def test_system_prompt_lists_every_channel():
    from pretext.models import Channel

    for channel in Channel:
        assert f'"{channel.value}"' in SYSTEM_PROMPT


def test_optional_fields_appear_only_when_set():
    plain = Profile(name="Ana Lima", role="Analyst", company="Cobalt", communication_style="Blunt")
    rich = Profile(
        name="Ana Lima",
        role="Analyst",
        company="Cobalt",
        communication_style="Blunt",
        department="Risk",
        systems=["ledger"],
    )
    assert "Department" not in build_payload_messages(plain)[1]["content"]
    content = build_payload_messages(rich)[1]["content"]
    assert "Department: Risk" in content
    assert "ledger" in content


def test_channel_and_extra_are_appended():
    profile = Profile(name="Ana Lima", role="Analyst", company="Cobalt", communication_style="Blunt")
    content = build_payload_messages(profile, channel="phone", extra="keep it brief")[1]["content"]
    assert "phone channel" in content
    assert "Additional direction: keep it brief" in content


def test_schema_keys_match_model_fields():
    import re

    from pretext.models import EscalationStep, RedFlag, Simulation

    schema = SYSTEM_PROMPT[SYSTEM_PROMPT.index("{"):SYSTEM_PROMPT.index("\n}\n\nRules")]
    top = set(re.findall(r'^  "(\w+)":', schema, re.MULTILINE))
    assert top == set(Simulation.model_fields)

    step = schema[schema.index("escalation_path"):schema.index("red_flags")]
    assert set(re.findall(r'^      "(\w+)":', step, re.MULTILINE)) == set(
        EscalationStep.model_fields
    )
    flags = schema[schema.index("red_flags"):]
    assert set(re.findall(r'"(\w+)":', flags)) == set(RedFlag.model_fields)
