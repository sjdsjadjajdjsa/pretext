"""Command line entry point."""

from __future__ import annotations

import json
import sys
from enum import Enum
from importlib import resources
from pathlib import Path

import typer
from pydantic import ValidationError
from rich.table import Table

from . import __version__, render
from .client import Client, _content_of, extract_json
from .models import (
    ENV_PREFIX,
    PROVIDERS,
    Channel,
    ConfigError,
    PretextError,
    Profile,
    ProfileError,
    Simulation,
    _format_validation,
    load_profile,
    profile_from_json,
    resolve_settings,
)
from .prompt import dump_prompt

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Generate labeled social-engineering simulations for authorized training.",
)


def _version(value: bool) -> None:
    if value:
        typer.echo(f"pretext {__version__}")
        raise typer.Exit()


@app.callback()
def root(
    version: bool = typer.Option(
        False, "--version", "-V", is_eager=True, callback=_version, help="Show the version."
    ),
) -> None:
    """Labeled social-engineering simulations for authorized training."""


class OutputFormat(str, Enum):
    rich = "rich"
    json = "json"
    markdown = "markdown"


def _read_profile(path: Path):
    if str(path) == "-":
        return profile_from_json(sys.stdin.read())
    return load_profile(path)


def _read_response(path: Path) -> tuple[Profile | None, Simulation]:
    """Read a saved response: our own export, a bare simulation, or a chat body."""

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ProfileError(f"cannot read response {path}: {exc.strerror or exc}") from exc
    except json.JSONDecodeError as exc:
        raise ProfileError(f"response {path} is not JSON: {exc}") from exc

    if not isinstance(document, dict):
        raise ProfileError(f"response {path} must be a JSON object")

    profile = None
    if isinstance(document.get("profile"), dict):
        profile = Profile.model_validate(document["profile"])

    raw = document.get("simulation", document)
    if isinstance(document.get("choices"), list):
        raw = extract_json(_content_of(document))

    try:
        return profile, Simulation.model_validate(raw)
    except ValidationError as exc:
        raise ProfileError(_format_validation(exc, prefix=f"invalid response {path}")) from exc


def _warnings(settings, profile=None) -> list[str]:
    warnings: list[str] = []
    if settings.base_url.scheme != "https":
        warnings.append("endpoint is not HTTPS; the API key travels in clear text")
    host = settings.base_url.host or ""
    if host in {"localhost", "127.0.0.1"}:
        warnings.append(f"endpoint is local ({host}); fine for a proxy or test server")
    if settings.temperature > 1.2:
        warnings.append("temperature above 1.2 often breaks the JSON contract")
    if profile is not None and profile.company.lower() in {"acme", "example", "example corp"}:
        warnings.append(f"company {profile.company!r} is generic; add specifics")
    return warnings


@app.command()
def generate(
    profile: Path = typer.Argument(
        None, metavar="[PROFILE]", help="YAML profile, or - to read JSON from stdin."
    ),
    base_url: str = typer.Option(
        None, "--base-url", "-u", help=f"API root [{ENV_PREFIX}BASE_URL]."
    ),
    model: str = typer.Option(None, "--model", "-m", help=f"Model name [{ENV_PREFIX}MODEL]."),
    api_key: str = typer.Option(
        None, "--api-key", "-k", help=f"Bearer token [{ENV_PREFIX}API_KEY, OPENAI_API_KEY]."
    ),
    provider: str = typer.Option(
        None,
        "--provider",
        "-p",
        help=f"Preset base URL: {', '.join(PROVIDERS)}. --base-url wins.",
    ),
    channel: Channel | None = typer.Option(
        None, "--channel", "-c", help="Force the opening channel."
    ),
    temperature: float = typer.Option(
        None, "--temperature", "-t", min=0.0, max=2.0, help="Sampling temperature."
    ),
    max_tokens: int = typer.Option(None, "--max-tokens", min=256, max=16000),
    timeout: float = typer.Option(None, "--timeout", min=1.0, max=600.0, help="Seconds."),
    retries: int = typer.Option(None, "--retries", min=0, max=8, help="Retry count on 429/5xx."),
    seed: int = typer.Option(None, "--seed", help="Sampling seed, if supported."),
    extra: str = typer.Option(None, "--extra", help="Extra direction for the model."),
    fmt: OutputFormat = typer.Option(OutputFormat.rich, "--format", "-f", help="Output format."),
    out_file: Path = typer.Option(None, "--out", "-o", help="Write output to this file."),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Resolve config and print the prompt; call nothing. --out writes the prompt.",
    ),
    response_file: Path = typer.Option(
        None, "--from-file", help="Render a saved response instead of calling the API."
    ),
    sections: str = typer.Option(
        None, "--sections", help="Comma list of: pretext, opening, escalation, red_flags."
    ),
    usage: bool = typer.Option(False, "--usage", help="Print token usage to stderr."),
    no_color: bool = typer.Option(False, "--no-color", help="Disable ANSI color."),
) -> None:
    """Generate one simulation from a profile."""

    out = render.console(no_color=no_color)
    err = render.console(no_color=no_color, stderr=True)

    selected: tuple[str, ...] = render.SECTIONS
    if sections is not None:
        selected = tuple(part.strip() for part in sections.split(",") if part.strip())
        unknown = [part for part in selected if part not in render.SECTIONS]
        if unknown or not selected:
            err.print(
                f"[bold red]error[/bold red] unknown section(s): {', '.join(unknown) or 'none'}; "
                f"choose from {', '.join(render.SECTIONS)}"
            )
            raise typer.Exit(2)

    if profile is None and response_file is None:
        err.print("[bold red]error[/bold red] pass a PROFILE or --from-file")
        raise typer.Exit(2)

    saved = None
    try:
        if response_file is not None:
            saved_profile, saved = _read_response(response_file)
            if profile is None:
                if saved_profile is None:
                    raise ProfileError(
                        f"response {response_file} has no profile; pass a PROFILE too"
                    )
                prof = saved_profile
        if profile is not None:
            prof = _read_profile(profile)
        settings = resolve_settings(
            provider=provider,
            base_url=base_url,
            model=model,
            api_key=api_key or ("unused" if saved is not None else None),
            temperature=temperature,
            timeout=timeout,
            retries=retries,
            max_tokens=max_tokens,
            seed=seed,
            dotenv=Path.cwd() / ".env",
        )
    except PretextError as exc:
        err.print(f"[bold red]error[/bold red] {exc}")
        raise typer.Exit(1) from exc

    warnings = _warnings(settings, prof)

    if dry_run:
        err.print("[bold]dry run[/bold] · nothing is sent")
        render.render_settings(settings, err)
        render.render_profile(prof, err)
        render.render_warnings(warnings, err)
        prompt = dump_prompt(prof, channel=channel.value if channel else None, extra=extra)
        if out_file is None:
            err.print()
            typer.echo(prompt)
        else:
            out_file.write_text(prompt + "\n", encoding="utf-8")
            err.print(f"wrote prompt to {out_file}")
        raise typer.Exit(0)

    render.render_warnings(warnings, err)

    client = Client(settings)
    if saved is not None:
        simulation = saved
        err.print(f"[dim]replayed {response_file}[/dim]")
    else:
        try:
            with err.status("[cyan]requesting simulation…[/cyan]", spinner="dots"):
                simulation = client.generate(
                    prof, channel=channel.value if channel else None, extra=extra
                )
        except PretextError as exc:
            err.print(f"[bold red]error[/bold red] {exc}")
            raise typer.Exit(1) from exc
        except KeyboardInterrupt:
            err.print("[yellow]interrupted[/yellow]")
            raise typer.Exit(130) from None

    if usage:
        tokens = client.last_usage or {}
        err.print(
            f"[dim]tokens: prompt {tokens.get('prompt_tokens', '?')} · "
            f"completion {tokens.get('completion_tokens', '?')} · "
            f"total {tokens.get('total_tokens', '?')}[/dim]"
        )

    if fmt is OutputFormat.json:
        body = render.to_json(simulation, prof, sections=selected)
    elif fmt is OutputFormat.markdown:
        body = render.to_markdown(simulation, prof, sections=selected)
    else:
        body = None

    if out_file is not None:
        if body is None:
            recording = render.console(no_color=True, width=100)
            with recording.capture() as captured:
                render.render_simulation(simulation, prof, recording, sections=selected)
            body = captured.get()
        out_file.write_text(body, encoding="utf-8")
        err.print(f"wrote {out_file}")
        return

    if body is not None:
        typer.echo(body)
    else:
        render.render_simulation(simulation, prof, out, sections=selected)


@app.command()
def validate(profile: Path = typer.Argument(..., metavar="PROFILE")) -> None:
    """Check a profile without calling the API."""

    out = render.console()
    try:
        prof = _read_profile(profile)
    except PretextError as exc:
        render.console(stderr=True).print(f"[bold red]invalid[/bold red] {exc}")
        raise typer.Exit(1) from exc
    render.render_profile(prof, out)


@app.command()
def example(
    out_file: Path = typer.Option(None, "--out", "-o", help="Write instead of printing."),
) -> None:
    """Print the bundled example profile."""

    text = (
        resources.files("pretext").joinpath("data/example-profile.yaml").read_text(encoding="utf-8")
    )
    if out_file is None:
        typer.echo(text, nl=False)
    else:
        out_file.write_text(text, encoding="utf-8")
        typer.echo(f"wrote {out_file}")


@app.command("config")
def show_config(
    provider: str = typer.Option(None, "--provider", "-p", help=f"Preset: {', '.join(PROVIDERS)}."),
    base_url: str = typer.Option(None, "--base-url", "-u"),
    model: str = typer.Option(None, "--model", "-m"),
    api_key: str = typer.Option(None, "--api-key", "-k"),
) -> None:
    """Show the configuration that would be used, with the key masked."""

    out = render.console()
    err = render.console(stderr=True)
    try:
        settings = resolve_settings(
            provider=provider,
            base_url=base_url,
            model=model,
            api_key=api_key,
            dotenv=Path.cwd() / ".env",
        )
    except ConfigError as exc:
        err.print(f"[bold red]error[/bold red] {exc}")
        raise typer.Exit(1) from exc
    render.render_settings(settings, out)
    render.render_warnings(_warnings(settings), err)


def main() -> None:
    app()


if __name__ == "__main__":
    main()


@app.command()
def batch(
    directory: Path = typer.Argument(..., metavar="DIR", help="Directory of YAML profiles."),
    out_dir: Path = typer.Option(..., "--out-dir", "-o", help="Where to write each exercise."),
    fmt: OutputFormat = typer.Option(OutputFormat.markdown, "--format", "-f"),
    sections: str = typer.Option(None, "--sections", help="Comma list of sections to render."),
    extra: str = typer.Option(None, "--extra", help="Extra direction for the model."),
    base_url: str = typer.Option(
        None, "--base-url", "-u", help=f"API root [{ENV_PREFIX}BASE_URL]."
    ),
    model: str = typer.Option(None, "--model", "-m", help=f"Model name [{ENV_PREFIX}MODEL]."),
    api_key: str = typer.Option(
        None, "--api-key", "-k", help=f"Bearer token [{ENV_PREFIX}API_KEY, OPENAI_API_KEY]."
    ),
    provider: str = typer.Option(
        None,
        "--provider",
        "-p",
        help=f"Preset base URL: {', '.join(PROVIDERS)}. --base-url wins.",
    ),
    temperature: float = typer.Option(None, "--temperature", "-t", min=0.0, max=2.0),
    max_tokens: int = typer.Option(None, "--max-tokens", min=256, max=16000),
    timeout: float = typer.Option(None, "--timeout", min=1.0, max=600.0),
    retries: int = typer.Option(None, "--retries", min=0, max=8),
    seed: int = typer.Option(None, "--seed"),
    usage: bool = typer.Option(False, "--usage", help="Print token totals to stderr."),
    no_color: bool = typer.Option(False, "--no-color"),
) -> None:
    """Generate one exercise per profile in a directory."""

    err = render.console(no_color=no_color, stderr=True)
    selected: tuple[str, ...] = render.SECTIONS
    if sections is not None:
        selected = tuple(part.strip() for part in sections.split(",") if part.strip())
        unknown = [part for part in selected if part not in render.SECTIONS]
        if unknown or not selected:
            err.print(f"[bold red]error[/bold red] unknown section(s): {', '.join(unknown)}")
            raise typer.Exit(2)

    if not directory.is_dir():
        err.print(f"[bold red]error[/bold red] {directory} is not a directory")
        raise typer.Exit(1)

    profiles = sorted(p for p in directory.glob("*.yaml") if not p.name.startswith("_"))
    if not profiles:
        err.print(f"[bold red]error[/bold red] no *.yaml profiles in {directory}")
        raise typer.Exit(1)

    try:
        settings = resolve_settings(
            provider=provider,
            base_url=base_url,
            model=model,
            api_key=api_key,
            temperature=temperature,
            timeout=timeout,
            retries=retries,
            max_tokens=max_tokens,
            seed=seed,
            dotenv=Path.cwd() / ".env",
        )
    except PretextError as exc:
        err.print(f"[bold red]error[/bold red] {exc}")
        raise typer.Exit(1) from exc

    out_dir.mkdir(parents=True, exist_ok=True)
    client = Client(settings)
    suffix = {"markdown": "md", "json": "json", "rich": "txt"}[fmt.value]
    failures: list[tuple[str, str]] = []
    totals = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    for index, path in enumerate(profiles, start=1):
        label = f"[cyan]{index}/{len(profiles)}[/cyan] {path.name}"
        try:
            prof = load_profile(path)
            simulation = client.generate(prof, channel=None, extra=extra)
        except PretextError as exc:
            failures.append((path.name, str(exc).splitlines()[0]))
            err.print(f"{label} [red]failed[/red] {failures[-1][1]}")
            continue

        for key in totals:
            totals[key] += (client.last_usage or {}).get(key, 0)

        target = out_dir / f"{path.stem}.{suffix}"
        if fmt is OutputFormat.json:
            body = render.to_json(simulation, prof, sections=selected)
        elif fmt is OutputFormat.markdown:
            body = render.to_markdown(simulation, prof, sections=selected)
        else:
            recording = render.console(no_color=True, width=100)
            with recording.capture() as captured:
                render.render_simulation(simulation, prof, recording, sections=selected)
            body = captured.get()
        target.write_text(body, encoding="utf-8")
        err.print(f"{label} [green]ok[/green] {target.name}")

    err.print()
    err.print(f"wrote {len(profiles) - len(failures)}/{len(profiles)} to {out_dir}")
    if usage:
        err.print(
            f"[dim]tokens: prompt {totals['prompt_tokens']} · "
            f"completion {totals['completion_tokens']} · total {totals['total_tokens']}[/dim]"
        )
    for name, reason in failures:
        err.print(f"[red]{name}[/red] {reason}")
    if failures:
        raise typer.Exit(1)


@app.command()
def doctor(
    base_url: str = typer.Option(
        None, "--base-url", "-u", help=f"API root [{ENV_PREFIX}BASE_URL]."
    ),
    model: str = typer.Option(None, "--model", "-m", help=f"Model name [{ENV_PREFIX}MODEL]."),
    api_key: str = typer.Option(
        None, "--api-key", "-k", help=f"Bearer token [{ENV_PREFIX}API_KEY, OPENAI_API_KEY]."
    ),
    provider: str = typer.Option(
        None,
        "--provider",
        "-p",
        help=f"Preset base URL: {', '.join(PROVIDERS)}. --base-url wins.",
    ),
    full: bool = typer.Option(False, "--full", help="Also run one real simulation."),
    no_color: bool = typer.Option(False, "--no-color"),
) -> None:
    """Diagnose the endpoint before spending a run on it."""

    out = render.console(no_color=no_color)
    err = render.console(no_color=no_color, stderr=True)
    results: list[tuple[str, str, str]] = []

    def record(name: str, status: str, detail: str) -> None:
        results.append((name, status, detail))

    try:
        settings = resolve_settings(
            provider=provider,
            base_url=base_url,
            model=model,
            api_key=api_key,
            dotenv=Path.cwd() / ".env",
        )
        record("configuration", "pass", f"{settings.base_url} · {settings.model}")
    except PretextError as exc:
        record("configuration", "fail", str(exc))
        _render_checks(results, out)
        raise typer.Exit(1) from exc

    if settings.base_url.scheme != "https":
        record("tls", "warn", "not HTTPS; the key is sent in clear text")
    else:
        record("tls", "pass", "HTTPS")

    client = Client(settings)
    try:
        models = client.list_models()
        record("endpoint", "pass", "reached /models")
        if not models:
            record("model", "warn", "endpoint lists no models; cannot verify the name")
        elif settings.model in models:
            record("model", "pass", f"{settings.model} is served")
        else:
            near = [m for m in models if m.split("/")[-1] in settings.model.split("/")[-1]][:3]
            hint = f"; did you mean {', '.join(near)}" if near else ""
            record("model", "fail", f"{settings.model} is not in the model list{hint}")
    except PretextError as exc:
        record("endpoint", "fail", str(exc))

    try:
        parsed = extract_json(client.ping_json())
        record("json mode", "pass", f"returned {', '.join(sorted(parsed)) or 'an empty object'}")
    except PretextError as exc:
        record("json mode", "fail", str(exc))

    if full:
        probe = Profile(
            name="Test Persona",
            role="Analyst",
            company="Northwind",
            communication_style="Plain and brief",
        )
        try:
            simulation = client.generate(probe)
            record(
                "schema",
                "pass",
                f"{len(simulation.escalation_path)} stages, {len(simulation.red_flags)} flags",
            )
        except PretextError as exc:
            record("schema", "fail", str(exc).splitlines()[0])

    _render_checks(results, out)
    if any(status == "fail" for _, status, _ in results):
        raise typer.Exit(1)
    if not full:
        err.print("[dim]add --full to test schema adherence too[/dim]")


def _render_checks(results: list[tuple[str, str, str]], out) -> None:
    marks = {
        "pass": "[green]pass[/green]",
        "warn": "[yellow]warn[/yellow]",
        "fail": "[red]fail[/red]",
    }
    table = Table(show_header=True, box=None, header_style="bold")
    table.add_column("check")
    table.add_column("")
    table.add_column("detail", overflow="fold")
    for name, status, detail in results:
        table.add_row(name, marks[status], detail)
    out.print(table)


@app.command()
def schema(
    everything: bool = typer.Option(False, "--all", help="Include the profile schema too."),
) -> None:
    """Print the JSON Schema the model output must satisfy."""

    payload = {"simulation": Simulation.model_json_schema()}
    if everything:
        payload["profile"] = Profile.model_json_schema()
    typer.echo(json.dumps(payload, indent=2))
