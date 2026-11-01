# Changelog

All notable changes. This project follows semantic versioning.

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
