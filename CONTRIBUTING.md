# Contributing

Thanks for helping. Bugs, prompt quality reports, and new output formats are all
welcome.

## Setup

```sh
uv sync --extra dev
uv run pytest --cov=pretext   # CI fails under 97% coverage
uv run ruff check src tests
uv run mypy
```

The suite is offline: `httpx.MockTransport` in `tests/test_client.py` and a stubbed
`Client` in `tests/test_cli.py`. Do not add tests that need a key or the network.
`tests/conftest.py` chdirs every test into a temp directory so your own `.env`
cannot leak in; keep that isolation.

## Ground rules

- Output must stay validated. Model text is rendered only after it passes
  `Simulation`, never before.
- stdout carries the payload, stderr carries diagnostics. `-f json` has to remain
  pipeable.
- New config options need all four touch points: `Settings` field, `resolve_settings`
  precedence row, `PRETEXT_*` env name, CLI flag.
- A new output format must include `render.DISCLAIMER`.
- Keep fixtures fictional and free of real company names, domains, and keys.
- Any prompt change: check `--dry-run` output and, if you have an endpoint, one
  real generation before opening the PR.

## Pull requests

One concern per PR. Describe the training scenario that motivated it. Fill in the
checklist. If a change alters the JSON schema, say so in the PR and update
`SYSTEM_PROMPT` and `Simulation` together.

## Commit messages

Present tense, imperative, first line under 72 characters, explaining why the
change exists. Conventional prefixes (`feat:`, `fix:`, `docs:`) are fine but not
required.

## Reporting security issues

See `SECURITY.md`. Never paste an API key into an issue.
