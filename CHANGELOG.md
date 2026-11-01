# Changelog

All notable changes. This project follows semantic versioning.

## Unreleased

- Distribution renamed `pretext-sim` (the `pretext` name belongs to PreTeXt); the
  command stays `pretext`
- PyPI publish workflow on release, via trusted publishing

- `docs/running-an-exercise.md`: authorization, delivery, scoring, debrief
- Model corpus with structural invariant tests, and clear errors when a thinking
  model runs out of output budget
- `schema` dumps the JSON Schema for integrators and drift checks
- `--provider` preset for openai, openrouter, venice, ollama and lmstudio
- `doctor` probes config, TLS, reachability, model availability and JSON mode,
  with `--full` to test schema adherence
- `batch` generates one exercise per profile in a directory, continuing past failures
- `--dry-run --out` writes the prompt instead of ignoring `--out`
- Verified against Venice (venice-uncensored-1-2, qwen3-235b-a22b-instruct)

## 0.3.0

- `doctor` diagnoses configuration, TLS, reachability, model availability and JSON
  mode, with `--full` for schema adherence
- `batch` generates one exercise per profile and reports failures via the exit code
- `--provider` preset for openai, openrouter, venice, ollama and lmstudio
- `schema` dumps the JSON Schema of the output contract
- `--dry-run --out` writes the prompt
- Thinking models that exhaust their budget now say so instead of returning empty
- Long objectives trimmed like artifacts
- mypy, `ruff format`, a 97% coverage gate and a release workflow in CI
- `docs/running-an-exercise.md`: authorization, delivery, scoring, debrief
- Model corpus with structural invariant tests

## 0.2.0

- `--from-file` replays a saved export, bare simulation, or chat body with no API
  call and no key
- `--sections` renders a subset of the exercise
- `--usage` reports token counts on stderr
- Openings must land on the ask and identify the sender; "sent from X, referencing Y"
  narration rejected in the prompt
- Opening-message validator strips `Subject:`/`From:` header lines the model repeats
- Overlong stage artifacts are trimmed instead of failing the whole run
- Prompt now forbids the attacker impersonating the persona, requires an in-body
  sending address, distinct non-adjacent channels, and a new prop per stage
- Fixture personas, prompt invariant tests, and render tests over a captured response
- Tests pin terminal width; the suite is deterministic across widths
- OpenRouter-tested across four models; `uv.lock` committed and Dependabot moved to
  the `uv` ecosystem
- Coverage gate at 97% (currently 99%) and fuzz coverage for JSON extraction

## 0.1.0

First release.

- `generate`, `validate`, `example`, and `config` commands
- YAML profile with strict validation and blank-to-null optionals
- OpenAI-compatible httpx client with retry/backoff on 429/5xx and transport errors
- pydantic-validated simulation schema with ordered escalation stages
- Rich terminal, Markdown, and JSON output; `--out` file export
- `--dry-run` prints resolved config and the exact prompt, sends nothing
- Config precedence across flags, `PRETEXT_*` env, `.env`, `OPENAI_API_KEY`
- Diagnostics on stderr so piped JSON stays clean
