from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from pretext.models import (
    ConfigError,
    Profile,
    ProfileError,
    Simulation,
    load_profile,
    profile_from_json,
    resolve_settings,
)

PROFILE_YAML = """
name: Dana Iyer
role: Senior Payroll Analyst
company: Northwind Logistics
communication_style: Brisk and formal, mirrors the sender
"""


def write(tmp_path, text: str, name: str = "p.yaml"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_load_profile_minimal(tmp_path):
    profile = load_profile(write(tmp_path, PROFILE_YAML))
    assert profile.name == "Dana Iyer"
    assert profile.systems == []


def test_load_profile_rejects_unknown_keys(tmp_path):
    with pytest.raises(ProfileError, match="company_typo"):
        load_profile(write(tmp_path, PROFILE_YAML + "company_typo: x\n"))


def test_load_profile_missing_field(tmp_path):
    with pytest.raises(ProfileError, match="role"):
        load_profile(write(tmp_path, "name: Dana\ncompany: Northwind\n"))


def test_blank_optional_becomes_none(tmp_path):
    profile = load_profile(write(tmp_path, PROFILE_YAML + "notes: '   '\n"))
    assert profile.notes is None


def test_duplicate_systems(tmp_path):
    with pytest.raises(ProfileError, match="duplicates"):
        load_profile(write(tmp_path, PROFILE_YAML + "systems: [a, a]\n"))


def test_profile_from_json_ok():
    payload = json.dumps(
        {"name": "Dana", "role": "Analyst", "company": "Northwind", "communication_style": "Brisk"}
    )
    assert profile_from_json(payload).name == "Dana"


def test_settings_precedence_flag_over_env(monkeypatch):
    monkeypatch.setenv("PRETEXT_BASE_URL", "http://env.example/v1")
    monkeypatch.setenv("PRETEXT_API_KEY", "env-key")
    settings = resolve_settings(base_url="http://flag.example/v1", dotenv=None)
    assert str(settings.base_url).startswith("http://flag.example")
    assert settings.endpoint == "http://flag.example/v1/chat/completions"


def test_settings_reads_dotenv(tmp_path, monkeypatch):
    monkeypatch.delenv("PRETEXT_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    dotenv = write(tmp_path, "PRETEXT_API_KEY=from-file\n", ".env")
    settings = resolve_settings(dotenv=dotenv)
    assert settings.api_key == "from-file"
    assert "from-file" not in repr(settings)


def test_settings_openai_key_fallback(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.delenv("PRETEXT_API_KEY", raising=False)
    assert resolve_settings(dotenv=None).api_key == "openai-key"


def test_settings_missing_key(monkeypatch):
    monkeypatch.delenv("PRETEXT_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ConfigError, match="no API key"):
        resolve_settings(dotenv=None)


def test_settings_bad_url():
    with pytest.raises(ConfigError, match="base_url"):
        resolve_settings(base_url="not a url", api_key="k", dotenv=None)


def test_settings_bad_temperature():
    with pytest.raises(ConfigError, match="temperature"):
        resolve_settings(api_key="k", temperature=9, dotenv=None)


STEPS = [
    {"stage": 1, "channel": "email", "action": "Send a fake invoice query.", "goal": "Open a thread"},
    {"stage": 2, "channel": "phone", "action": "Call to confirm the invoice.", "goal": "Get a callback"},
]

FLAGS = [
    {"title": "Odd domain", "why_it_matters": "Vendor mail came from elsewhere.", "defender_action": "Check the domain"},
    {"title": "Urgency", "why_it_matters": "Deadline is same day.", "defender_action": "Verify out of band"},
]


def simulation_payload(**over):
    payload = {
        "pretext": "x" * 100,
        "opening_message": "Hi Dana, quick one on the invoice.",
        "escalation_path": STEPS,
        "red_flags": FLAGS,
        "difficulty": 3,
    }
    payload.update(over)
    return payload


def test_simulation_accepts_valid_payload():
    sim = Simulation.model_validate(simulation_payload())
    assert sim.escalation_path[1].stage == 2


def test_simulation_requires_sequenced_stages():
    broken = [dict(STEPS[0], stage=2), dict(STEPS[1], stage=4)]
    with pytest.raises(ValidationError, match=r"1\.\.n"):
        Simulation.model_validate(simulation_payload(escalation_path=broken))


def test_simulation_rejects_short_escalation():
    with pytest.raises(ValidationError):
        Simulation.model_validate(simulation_payload(escalation_path=STEPS[:1]))


def test_simulation_rejects_unknown_keys():
    with pytest.raises(ValidationError, match="extra_forbidden"):
        Simulation.model_validate(simulation_payload(pretend="yes"))


def test_channel_enum_enforced():
    bad = [dict(STEPS[0], channel="carrier_pigeon"), STEPS[1]]
    with pytest.raises(ValidationError):
        Simulation.model_validate(simulation_payload(escalation_path=bad))


def test_settings_numeric_from_dotenv(tmp_path, monkeypatch):
    for key in ("PRETEXT_RETRIES", "PRETEXT_TEMPERATURE"):
        monkeypatch.delenv(key, raising=False)
    dotenv = write(tmp_path, "PRETEXT_API_KEY=k\nPRETEXT_RETRIES=1\nPRETEXT_TEMPERATURE=0.2\n", ".env")
    settings = resolve_settings(dotenv=dotenv)
    assert settings.retries == 1
    assert settings.temperature == 0.2


def test_settings_numeric_flag_beats_dotenv(tmp_path):
    dotenv = write(tmp_path, "PRETEXT_API_KEY=k\nPRETEXT_RETRIES=1\n", ".env")
    assert resolve_settings(dotenv=dotenv, retries=5).retries == 5


def test_settings_numeric_rejects_junk(tmp_path):
    dotenv = write(tmp_path, "PRETEXT_API_KEY=k\nPRETEXT_RETRIES=lots\n", ".env")
    with pytest.raises(ConfigError, match="retries"):
        resolve_settings(dotenv=dotenv)


def test_opening_message_headers_stripped():
    payload = simulation_payload(
        opening_message="Subject: Hi\nFrom: a@b.co\n\nActual body here, long enough."
    )
    sim = Simulation.model_validate(payload)
    assert sim.opening_message == "Actual body here, long enough."


def test_opening_message_without_headers_untouched():
    sim = Simulation.model_validate(simulation_payload())
    assert sim.opening_message.startswith("Hi Dana")


def test_blank_to_none_handles_none():
    assert Profile(name="Ana", role="Analyst", company="Cobalt", communication_style="Blunt", notes=None).notes is None


def test_stage_coerced_from_string():
    from pretext.models import EscalationStep

    assert EscalationStep.model_validate(
        {"stage": "2", "channel": "email", "action": "Send the thing.", "goal": "Open thread"}
    ).stage == 2


def test_dotenv_skips_comments_and_junk(tmp_path, monkeypatch):
    monkeypatch.delenv("PRETEXT_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    dotenv = write(tmp_path, "# note\n\nbroken\nPRETEXT_API_KEY='quoted'\n", ".env")
    assert resolve_settings(dotenv=dotenv).api_key == "quoted"


def test_profile_empty_file(tmp_path):
    with pytest.raises(ProfileError, match="empty"):
        load_profile(write(tmp_path, ""))


def test_profile_not_a_mapping(tmp_path):
    with pytest.raises(ProfileError, match="mapping"):
        load_profile(write(tmp_path, "- a\n- b\n"))


def test_profile_invalid_yaml(tmp_path):
    with pytest.raises(ProfileError, match="invalid YAML"):
        load_profile(write(tmp_path, "name: [unclosed\n"))


def test_profile_from_json_invalid():
    with pytest.raises(ProfileError, match="invalid profile JSON"):
        profile_from_json('{"name": "x"}')
