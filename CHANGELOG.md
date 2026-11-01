# Changelog

All notable changes. This project follows semantic versioning.

## Unreleased

- `batch` generates one exercise per profile in a directory, continuing past failures
- `--dry-run --out` writes the prompt instead of ignoring `--out`
- Verified against Venice (venice-uncensored-1-2, qwen3-235b-a22b-instruct)

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
