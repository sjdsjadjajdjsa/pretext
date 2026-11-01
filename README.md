# pretext

Generate labeled social-engineering simulations you can hand to trainees.

`pretext` turns a one-page persona profile into a complete exercise: a pretext
narrative, a usable opening message, a staged escalation path, and a set of red
flags written for defenders. Output is validated and rendered in the terminal, or
exported to Markdown/JSON for a training packet.

> **Authorized training only.** Everything here is a fictional exercise. Domains,
> names, and systems produced by the model are invented unless you say otherwise.
> Nothing is sent to a target, so run exercises against your own people only after
> your security team has agreed to it, and keep the malware-free "no click" promise
> honest by checking lures before sending.

## Install

```sh
uv sync --extra dev
```

Python 3.10+.

## Configure

Any OpenAI-compatible chat completions endpoint works. Configuration resolves in
this order, first hit wins:

1. Flags: `--base-url`, `--model`, `--api-key`
2. Environment: `PRETEXT_BASE_URL`, `PRETEXT_MODEL`, `PRETEXT_API_KEY`,
   `PRETEXT_TEMPERATURE`, `PRETEXT_TIMEOUT`, `PRETEXT_RETRIES`,
   `PRETEXT_MAX_TOKENS`, `PRETEXT_SEED`
3. `.env` in the working directory, same names
4. `OPENAI_API_KEY` for the key, then the defaults
   `https://api.openai.com/v1` and `gpt-4o-mini`

`pretext config` shows the resolved values with the key masked.

```sh
export PRETEXT_BASE_URL=http://localhost:11434/v1   # e.g. a local proxy
export PRETEXT_MODEL=gpt-oss:20b
export PRETEXT_API_KEY=unused
```

## Profile

A profile is YAML. Only `name`, `role`, `company`, and `communication_style` are
required; `department`, `tenure`, `reports_to`, `systems`, and `notes` sharpen the
result and are all optional.

```yaml
name: Dana Iyer
role: Senior Payroll Analyst
company: Northwind Logistics
department: People Operations
tenure: 3 months
reports_to: Marta Kwan
communication_style: Brisk and formal, mixes payroll shorthand with chatty asides, mirrors whoever she is replying to
systems:
  - Workday
  - the payroll mailbox
  - the bank-change portal
notes: New enough to the team to be unsure of process, still learning who owns what.
```

All of these are fictional.

`pretext example` prints this profile; `pretext validate persona.yaml` checks yours
before you spend a request.

## Run

```sh
pretext generate persona.yaml
pretext generate persona.yaml --channel phone --format markdown --out exercise.md
pretext generate persona.yaml --dry-run      # config + exact prompt, no call
pretext generate - < persona.json            # JSON profile on stdin
pretext generate persona.yaml --usage        # token counts to stderr
pretext generate --from-file saved.json      # replay a saved response, no API call
```

Output formats: `rich` (default), `markdown`, `json`. `--out` writes to a file and
uses plain text when no format is chosen. `sample-output.md` is what a finished
Markdown export looks like.

`--from-file` renders a response you saved earlier: a `--format json` export, a
bare simulation object, or a raw chat completion body. Nothing is sent, no key is
needed, and the profile comes from the export (pass `PROFILE` for a bare object).
Use it to iterate on formatting for free.

The model returns strict JSON which is validated with pydantic before anything is
rendered. `escalation_path` stages must run 1..n with no gaps, `red_flags` needs at
least two entries, and the client rejects unknown keys, so a loosely prompted model
fails loudly instead of producing a half-filled exercise.

## Exit codes

| Code | Meaning |
| ---- | ------- |
| 0 | success, including `--dry-run` |
| 1 | bad profile, bad config, API failure, validation failure |
| 2 | CLI usage error |
| 130 | interrupted |

## Library use

```python
from pathlib import Path
from pretext import Client, load_profile, resolve_settings

profile = load_profile(Path("persona.yaml"))
settings = resolve_settings(base_url="http://localhost:11434/v1", model="local", api_key="x")
simulation = Client(settings).generate(profile, channel="email")
print(simulation.red_flags[0].defender_action)
```

## Development

```sh
uv pip install -e ".[dev]"
pytest
uv run ruff check src tests
```

Tests use `httpx.MockTransport`, so the suite needs no network and no key.
`--dry-run` and `pretext validate` are the fast ways to check a prompt change.

## Contributing

Issues and pull requests are welcome. `CONTRIBUTING.md` covers setup and the
rules that keep output validated and stdout pipeable. Run `pretext --version`
when filing a bug. Security reports follow `SECURITY.md`.

Fixtures must stay fictional: no real company names, domains, or keys in tests
or the example profile.

## Status

0.1.0, pre-1.0. The CLI surface and JSON schema can still move between minor
versions; `CHANGELOG.md` records what changed. Planned work: a batch mode over a
profile directory, a `--json-schema` dump for prompt debugging, and an offline
`--from-file` renderer that replays a saved model response.

Not planned: sending anything to a target, click tracking, or an SMTP client.
pretext produces the text and the analysis; delivery stays your job.

## Configuration notes

- `response_format: json_object` is sent on every request. If your endpoint rejects
  it, the response is still parsed wherever the object appears, so most proxies work.
- Retries cover 408/409/425/429/5xx and transport errors with jittered exponential
  backoff; `Retry-After` is honored up to 30s.
- The API key is never written to output and is masked in `pretext config`.
- Temperature above 1.2 tends to break the JSON contract; the CLI warns you.
