# AGENTS.md

CLI that turns a YAML persona into a labeled social-engineering simulation
(pretext, opening message, escalation path, defender red flags) via any
OpenAI-compatible chat completions endpoint.

## Setup and commands

```sh
uv venv --python 3.12 .venv
uv pip install -e ".[dev]"
.venv/bin/pytest              # suite is offline, httpx.MockTransport only
.venv/bin/ruff check src tests
.venv/bin/pretext --help
```

`uv` is the only supported installer; the venv is at `.venv` and is not on PATH.
There is no build step and no Makefile. `pytest` must pass with no network and no
API key, keep it that way.

## Layout and data flow

```
profile.yaml ──load_profile──> Profile ──prompt.build_payload_messages──> messages
                                              │
                        client.Client.generate ──httpx──> /chat/completions
                                              │
                        extract_json ──> Simulation.model_validate ──> render.*
                                              │
                             rich panel / markdown / json / file
```

| File | Role |
| ---- | ---- |
| `models.py` | `Profile`, `Simulation`, `Settings`; error classes; env/flag/`.env` resolution; YAML + JSON loaders |
| `prompt.py` | System prompt carrying the JSON schema, and the user prompt |
| `client.py` | httpx POST, retry policy, JSON extraction, response validation |
| `render.py` | Rich panels, markdown/JSON serializers, `DISCLAIMER` |
| `cli.py` | Typer commands: `generate`, `validate`, `example`, `config` |
| `data/example-profile.yaml` | Fictional persona used by `pretext example` and the README |

`resolve_settings` is the single place precedence lives: flag, then `PRETEXT_*`
env, then `./.env`, then `OPENAI_API_KEY`, then defaults. Every new option needs a
row there, an env name, a CLI flag, and a `Settings` field, else it silently never
resolves.

## Contract rules

- **stdout is payload, stderr is diagnostics.** The `err` console is
  `Console(stderr=True)`. Warnings, spinner, `wrote …`, and errors go to stderr so
  `pretext generate -f json | jq` stays parseable. Rendering goes to `out`.
  Breaking this is the most likely regression: assert on `result.stdout` vs
  `result.output` deliberately in tests.
- **Validate before rendering.** Model output goes through `Simulation` and every
  output format runs off that object. Never print raw model text or a partially
  filled panel; a schema failure must raise `APIError` with the pydantic details.
  `Simulation` forbids extra keys and requires `escalation_path` stages to be
  exactly `1..n`, so a model that invents a `stage 2` gap fails instead of
  producing a broken table.
- **Errors are `PretextError` subclasses** (`ConfigError`, `ProfileError`,
  `APIError`). The CLI catches them, prints to stderr, exits 1. Do not let raw
  `httpx` or `ValidationError` escape to the user, and do not catch them per
  command in a new way.
- **The persona is the target, not the sender.** The prompt says so explicitly
  because models default to having the attacker introduce themselves as the
  persona. The opening must name the sending address or number in the body, since
  `Subject:`/`From:` header lines are stripped by a validator on
  `opening_message` (`HEADER_PREFIXES`). Keep that validator if you touch the
  prompt.
- **The disclaimer travels with the exercise.** `render.DISCLAIMER` appears in the
  rich footer, the markdown footer, and the JSON `disclaimer` key. A new output
  format must include it.
- **Secrets never print.** `Settings.api_key` is `repr=False`; `pretext config`
  shows `set`/`missing`. Key must never reach `--format json` or a log line.

## Gotchas

- `Settings` is frozen and `HttpUrl`-typed. `non-https` is a warning, not an error,
  because local proxies are the main dev path.
- Retries cover only `{408,409,425,429,500,502,503,504}` and transport errors;
  `_request` re-enters `_decode` on the last attempt so the final 4xx/5xx detail
  reaches the user. `Retry-After` is honored to 30s. Don't add retries for 400/401.
- `extract_json` tolerates code fences, prose, and list-shaped `content` parts
  because proxies vary. Keep the fallback: endpoints may ignore
  `response_format: json_object`.
- Empty model content is an error, not an empty simulation.
- `--dry-run` still resolves settings, so it needs a key; it prints the prompt to
  stdout via `typer.echo` (unwrapped) and exits 0. `validate` needs no key.
- File output with the default rich format renders into a `Console.capture()`
  block; the render must happen inside the `with`, not after it.
- Typer options use `= typer.Option(None, ...)` defaults; resource resolution
  happens in the command body, never in the signature. `Channel | None` is written
  as a string annotation. Enum values are the wire values in the prompt schema,
  so adding a channel means touching `Channel` and `SYSTEM_PROMPT` together.
- Profile YAML forbids unknown keys on purpose (typo detection), and optional
  strings are blank-to-`None`. Tests rely on both.
- Company `Acme`/`example` and non-HTTPS endpoints trigger warnings; both are
  benign in tests.
- Everything in the example profile is fictional. Keep real vendor names out of
  the prompt's sample output.

## Repo hygiene

CI (`.github/workflows/ci.yml`) runs ruff, pytest, and a dry-run smoke on Python
3.10-3.13; the local equivalents are `ruff check src tests` and `pytest`. Test
files are exempt from E501, source files are not. Releasing means bumping
`__version__` in `__init__.py`, `version` in `pyproject.toml`, adding a
`CHANGELOG.md` entry, then `uv build`. `SECURITY.md` and `CONTRIBUTING.md` are
user-facing; changes to the schema or CLI need a line there when behaviour moves.

## Tests

`conftest.py` chdirs every test into a fresh temp directory, so the developer's
real `.env` never leaks into resolution; keep that fixture autouse.

`tests/test_client.py` drives the client through `httpx.MockTransport` and
monkeypatches `time.sleep`; add cases there rather than hitting the network.
`tests/test_cli.py` swaps `cli.Client` for a stub, so command behaviour is tested
without HTTP. Cover the failure path (retry exhaustion, schema violation, bad
key) whenever you touch the client or schema. `tests/test_models.py` owns
precedence and validation edge cases.

`sample-output.md` is a real `gpt-4o-mini` run through OpenRouter, kept as the
quality bar. Prompt changes should be compared against it; a run costs well under
a cent, so use `--usage` and a real endpoint instead of guessing.

Manual end-to-end without a key: run any throwaway HTTP server that returns
`{"choices":[{"message":{"content":"<json>"}}]}` and point
`--base-url http://127.0.0.1:PORT/v1` at it. `--dry-run` is the fast check for a
prompt edit.
