from __future__ import annotations

import json
from typing import ClassVar

import pytest
from typer.testing import CliRunner

from pretext import cli
from pretext.models import APIError, Simulation

RUNNER = CliRunner()

PROFILE_YAML = """
name: Dana Iyer
role: Senior Payroll Analyst
company: Northwind Logistics
communication_style: Brisk and formal, mirrors the sender
"""

PAYLOAD = {
    "pretext": "x" * 100,
    "opening_message": "Hi Dana, quick one on the invoice.",
    "subject_line": "Invoice 4471",
    "objective": "Get the bank details changed",
    "escalation_path": [
        {"stage": 1, "channel": "email", "action": "Send a fake invoice query.", "goal": "Open a thread"},
        {"stage": 2, "channel": "phone", "action": "Call to confirm the invoice.", "goal": "Get a callback", "artifact": "Callback number"},
    ],
    "red_flags": [
        {"title": "Odd domain", "why_it_matters": "Vendor mail came from elsewhere.", "defender_action": "Check the domain"},
        {"title": "Urgency", "why_it_matters": "Deadline is same day.", "defender_action": "Verify out of band"},
    ],
    "difficulty": 4,
}


class StubClient:
    calls: ClassVar[list[tuple]] = []
    error: ClassVar[Exception | None] = None
    last_usage: ClassVar[dict | None] = {
        "prompt_tokens": 1,
        "completion_tokens": 2,
        "total_tokens": 3,
    }

    def __init__(self, settings):
        self.settings = settings

    def generate(self, profile, *, channel=None, extra=None):
        StubClient.calls.append((profile.name, channel, extra, str(self.settings.base_url)))
        if StubClient.error:
            raise StubClient.error
        return Simulation.model_validate(PAYLOAD)


@pytest.fixture(autouse=True)
def stub(monkeypatch):
    StubClient.calls = []
    StubClient.error = None
    monkeypatch.setattr(cli, "Client", StubClient)
    monkeypatch.delenv("PRETEXT_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


@pytest.fixture
def profile(tmp_path):
    path = tmp_path / "persona.yaml"
    path.write_text(PROFILE_YAML, encoding="utf-8")
    return path


def run(*args):
    return RUNNER.invoke(cli.app, [str(a) for a in args])


def test_validate_ok(profile):
    result = run("validate", profile)
    assert result.exit_code == 0
    assert "Profile OK" in result.stdout


def test_validate_invalid(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("name: x\n", encoding="utf-8")
    result = run("validate", path)
    assert result.exit_code == 1
    assert "role" in result.output


def test_validate_missing_file(tmp_path):
    result = run("validate", tmp_path / "nope.yaml")
    assert result.exit_code == 1
    assert "cannot read profile" in result.output


def test_example_prints_yaml():
    result = run("example")
    assert result.exit_code == 0
    assert "communication_style:" in result.stdout


def test_example_to_file(tmp_path):
    target = tmp_path / "p.yaml"
    result = run("example", "--out", target)
    assert result.exit_code == 0
    assert target.exists()


def test_dry_run_skips_api(profile):
    result = run("generate", profile, "--api-key", "sk-x", "--dry-run")
    assert result.exit_code == 0
    assert StubClient.calls == []
    assert "dry run" in result.output
    assert '"messages"' in result.stdout
    assert "Key" in result.output


def test_dry_run_without_key_fails(profile):
    result = run("generate", profile, "--dry-run")
    assert result.exit_code == 1
    assert "no API key" in result.output


def test_generate_renders(profile):
    result = run("generate", profile, "--api-key", "sk-x", "--base-url", "https://api.test/v1")
    assert result.exit_code == 0
    assert "Northwind Logistics" in result.stdout
    assert "Escalation path" in result.stdout
    assert "Red flags for defenders" in result.stdout
    assert "Authorized training" not in result.stdout
    assert "Fictional exercise." in result.stdout
    assert "! endpoint is not HTTPS" not in result.stdout


def test_generate_passes_channel_and_extra(profile):
    run("generate", profile, "--api-key", "sk-x", "--channel", "phone", "--extra", "short")
    assert StubClient.calls == [("Dana Iyer", "phone", "short", "https://api.openai.com/v1")]


def test_generate_json(profile):
    result = run("generate", profile, "--api-key", "sk-x", "--format", "json")
    body = json.loads(result.stdout)
    assert body["profile"]["name"] == "Dana Iyer"
    assert body["simulation"]["difficulty"] == 4
    assert "disclaimer" in body


def test_generate_markdown(profile):
    result = run("generate", profile, "--api-key", "sk-x", "--format", "markdown")
    assert result.exit_code == 0
    assert "# Social-engineering simulation: Dana Iyer" in result.stdout
    assert "2. **Urgency**" in result.stdout


def test_generate_out_file(profile, tmp_path):
    target = tmp_path / "out.md"
    result = run("generate", profile, "--api-key", "sk-x", "--format", "markdown", "--out", target)
    assert result.exit_code == 0
    assert "Dana Iyer" in target.read_text(encoding="utf-8")


def test_generate_out_file_rich_renders_text(profile, tmp_path):
    target = tmp_path / "out.txt"
    result = run("generate", profile, "--api-key", "sk-x", "--out", target)
    assert result.exit_code == 0
    assert "Escalation path" in target.read_text(encoding="utf-8")


def test_generate_api_error(profile):
    StubClient.error = APIError("HTTP 401: bad key")
    result = run("generate", profile, "--api-key", "sk-x")
    assert result.exit_code == 1
    assert "bad key" in result.output


def test_generate_rejects_bad_channel(profile):
    result = run("generate", profile, "--api-key", "sk-x", "--channel", "pigeon")
    assert result.exit_code == 2


def test_config_masks_key():
    result = RUNNER.invoke(cli.app, ["config", "--api-key", "sk-very-secret-value"])
    assert result.exit_code == 0
    assert "sk-very-secret-value" not in result.stdout
    assert "set" in result.stdout


def test_config_missing_key():
    result = RUNNER.invoke(cli.app, ["config"])
    assert result.exit_code == 1
    assert "no API key" in result.output


def test_version_flag():
    result = RUNNER.invoke(cli.app, ["--version"])
    assert result.exit_code == 0
    assert result.output.startswith("pretext ")


def test_usage_flag_prints_tokens(profile):
    result = run("generate", profile, "--api-key", "sk-x", "--usage", "--format", "json")
    assert result.exit_code == 0
    assert "tokens:" in result.output
