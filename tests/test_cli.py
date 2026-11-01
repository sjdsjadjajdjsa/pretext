from __future__ import annotations

import json
from pathlib import Path
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


def flat(result) -> str:
    """Output with wrapping removed, because Rich reflows to the runner's width."""

    return " ".join(result.output.split())


def flat_out(result) -> str:
    return " ".join(result.stdout.split())


def test_validate_ok(profile):
    result = run("validate", profile)
    assert result.exit_code == 0
    assert "Profile OK" in flat_out(result)


def test_validate_invalid(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("name: x\n", encoding="utf-8")
    result = run("validate", path)
    assert result.exit_code == 1
    assert "role" in flat(result)


def test_validate_missing_file(tmp_path):
    result = run("validate", tmp_path / "nope.yaml")
    assert result.exit_code == 1
    assert "cannot read profile" in flat(result)


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
    assert "dry run" in flat(result)
    assert '"messages"' in result.stdout
    assert "Key" in flat(result)


def test_dry_run_without_key_fails(profile):
    result = run("generate", profile, "--dry-run")
    assert result.exit_code == 1
    assert "no API key" in flat(result)


def test_generate_renders(profile):
    result = run("generate", profile, "--api-key", "sk-x", "--base-url", "https://api.test/v1")
    assert result.exit_code == 0
    assert "Dana" in flat_out(result)
    assert "Payroll" in flat_out(result)
    assert "Escalation" in flat_out(result)
    assert "Red flags" in flat_out(result)
    assert "Authorized training" not in result.stdout
    assert "Fictional exercise." in flat_out(result)
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
    assert "# Social-engineering simulation: Dana Iyer" in flat_out(result)
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
    assert "bad key" in flat(result)


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
    assert "no API key" in flat(result)


def test_version_flag():
    result = RUNNER.invoke(cli.app, ["--version"])
    assert result.exit_code == 0
    assert result.output.startswith("pretext ")


def test_usage_flag_prints_tokens(profile):
    result = run("generate", profile, "--api-key", "sk-x", "--usage", "--format", "json")
    assert result.exit_code == 0
    assert "tokens:" in flat(result)


FIXTURE = Path(__file__).parent / "fixtures" / "responses" / "dana.json"


def test_replay_wrapped_response(profile, tmp_path):
    result = RUNNER.invoke(cli.app, ["generate", "--from-file", str(FIXTURE), "-f", "markdown"])
    assert result.exit_code == 0
    assert "Social-engineering simulation" in flat_out(result)
    assert "Escalation" in flat_out(result)
    assert StubClient.calls == []
    assert "replayed" in flat(result)


def test_replay_needs_no_key(tmp_path):
    result = RUNNER.invoke(cli.app, ["generate", "--from-file", str(FIXTURE), "-f", "json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["simulation"]["difficulty"]


def test_replay_requires_profile_when_bare(tmp_path):
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    bare = tmp_path / "bare.json"
    bare.write_text(json.dumps(data["simulation"]), encoding="utf-8")
    result = RUNNER.invoke(cli.app, ["generate", "--from-file", str(bare)])
    assert result.exit_code == 1
    assert "pass a PROFILE too" in flat(result)


def test_replay_bare_with_profile_argument(tmp_path, profile):
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    bare = tmp_path / "bare.json"
    bare.write_text(json.dumps(data["simulation"]), encoding="utf-8")
    result = RUNNER.invoke(cli.app, ["generate", str(profile), "--from-file", str(bare)])
    assert result.exit_code == 0
    assert "Escalation" in flat_out(result)


def test_replay_chat_body(tmp_path):
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    body = {"choices": [{"message": {"content": json.dumps(data["simulation"])}}]}
    wrapped = tmp_path / "body.json"
    wrapped.write_text(json.dumps(body), encoding="utf-8")
    result = RUNNER.invoke(cli.app, ["generate", str(FIXTURE.parent.parent / "profiles" / "helpdesk.yaml"),
                                     "--from-file", str(wrapped)])
    assert result.exit_code == 0


def test_replay_rejects_non_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("nope", encoding="utf-8")
    result = RUNNER.invoke(cli.app, ["generate", "--from-file", str(bad)])
    assert result.exit_code == 1
    assert "is not JSON" in flat(result)


def test_replay_rejects_schema_violation(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"pretext": "short"}), encoding="utf-8")
    result = RUNNER.invoke(cli.app, ["generate", "--from-file", str(bad)])
    assert result.exit_code == 1
    assert "invalid response" in flat(result)


def test_no_profile_and_no_file_is_usage_error():
    result = RUNNER.invoke(cli.app, ["generate"])
    assert result.exit_code == 2
    assert "pass a PROFILE or --from-file" in flat(result)


def test_sections_flag(profile):
    result = run("generate", profile, "--api-key", "sk-x", "--sections", "opening", "-f", "markdown")
    assert result.exit_code == 0
    assert "## Opening message" in result.stdout
    assert "## Pretext" not in result.stdout


def test_sections_rejects_unknown(profile):
    result = run("generate", profile, "--api-key", "sk-x", "--sections", "opening,bogus")
    assert result.exit_code == 2
    assert "bogus" in flat(result)


def test_profile_from_stdin():
    result = RUNNER.invoke(cli.app, ["validate", "-"], input=json.dumps({
        "name": "Ana Lima", "role": "Analyst", "company": "Cobalt",
        "communication_style": "Blunt",
    }))
    assert result.exit_code == 0
    assert "Profile OK" in flat_out(result)


def test_warnings_http_default_host(tmp_path):
    path = tmp_path / "p.yaml"
    path.write_text(PROFILE_YAML.replace("Northwind Logistics", "Acme"), encoding="utf-8")
    result = run("generate", path, "--api-key", "sk-x", "--base-url", "http://api.test/v1",
                 "--temperature", "1.5")
    assert result.exit_code == 0
    out = flat(result)
    assert "not HTTPS" in out
    assert "generic" in out
    assert "temperature above 1.2" in out


def test_keyboard_interrupt_exits_130(profile):
    StubClient.error = KeyboardInterrupt()
    result = run("generate", profile, "--api-key", "sk-x")
    assert result.exit_code == 130
    assert "interrupted" in flat(result)


def test_replay_missing_file(tmp_path):
    result = RUNNER.invoke(cli.app, ["generate", "--from-file", str(tmp_path / "gone.json")])
    assert result.exit_code == 1
    assert "cannot read response" in flat(result)


def test_replay_non_object(tmp_path):
    bad = tmp_path / "list.json"
    bad.write_text("[1]", encoding="utf-8")
    result = RUNNER.invoke(cli.app, ["generate", "--from-file", str(bad)])
    assert result.exit_code == 1
    assert "JSON object" in flat(result)


def test_main_entrypoint(monkeypatch):
    called = {}
    monkeypatch.setattr(cli, "app", lambda: called.setdefault("hit", True))
    cli.main()
    assert called["hit"]


def test_local_endpoint_warning(profile):
    result = run("generate", profile, "--api-key", "sk-x", "--base-url", "http://localhost:9/v1", "--dry-run")
    assert result.exit_code == 0
    assert "endpoint is local" in flat(result)


def test_dry_run_writes_prompt_file(profile, tmp_path):
    target = tmp_path / "prompt.json"
    result = run("generate", profile, "--api-key", "sk-x", "--dry-run", "--out", target)
    assert result.exit_code == 0
    assert json.loads(target.read_text(encoding="utf-8"))["messages"]
    assert "wrote prompt" in flat(result)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "profiles"


def test_batch_writes_one_file_per_profile(tmp_path):
    target = tmp_path / "packet"
    result = run("batch", FIXTURE_DIR, "--out-dir", target, "--api-key", "sk-x")
    assert result.exit_code == 0
    assert sorted(p.name for p in target.glob("*.md")) == [
        "exec-assistant.md", "finance.md", "helpdesk.md", "new-hire.md",
    ]
    assert "4/4" in flat(result)


def test_batch_isolates_failures(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "good.yaml").write_text(PROFILE_YAML, encoding="utf-8")
    (src / "bad.yaml").write_text("name: x\n", encoding="utf-8")
    target = tmp_path / "out"
    result = run("batch", src, "--out-dir", target, "--api-key", "sk-x")
    assert result.exit_code == 1
    assert (target / "good.md").exists()
    assert not (target / "bad.md").exists()
    assert "1/2" in flat(result)


def test_batch_skips_underscore_files(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "_partial.yaml").write_text("nope", encoding="utf-8")
    (src / "one.yaml").write_text(PROFILE_YAML, encoding="utf-8")
    result = run("batch", src, "--out-dir", tmp_path / "out", "--api-key", "sk-x")
    assert result.exit_code == 0
    assert "1/1" in flat(result)


def test_batch_empty_dir(tmp_path):
    result = run("batch", tmp_path, "--out-dir", tmp_path / "out", "--api-key", "sk-x")
    assert result.exit_code == 1
    assert "no *.yaml profiles" in flat(result)


def test_batch_not_a_directory(tmp_path):
    result = run("batch", tmp_path / "nope", "--out-dir", tmp_path / "out", "--api-key", "sk-x")
    assert result.exit_code == 1
    assert "not a directory" in flat(result)


def test_batch_sections_validated(tmp_path):
    result = run("batch", FIXTURE_DIR, "--out-dir", tmp_path, "--api-key", "sk-x", "--sections", "bogus")
    assert result.exit_code == 2
    assert "bogus" in flat(result)


def test_batch_usage_totals(tmp_path):
    result = run("batch", FIXTURE_DIR, "--out-dir", tmp_path, "--api-key", "sk-x", "--usage")
    assert result.exit_code == 0
    assert "total 12" in flat(result)
