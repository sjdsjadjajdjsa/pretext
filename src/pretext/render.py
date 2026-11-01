"""Rich rendering and plain-text export of simulations."""

from __future__ import annotations

import json
from collections.abc import Iterable

from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from .models import Profile, Settings, Simulation

DISCLAIMER = (
    "Fictional exercise. Domains, names, and systems are invented. "
    "Use against authorized targets only."
)
DIFFICULTY_LABELS = {
    1: "broad, high volume",
    2: "lightly targeted",
    3: "targeted",
    4: "researched, multi-step",
    5: "bespoke, multi-day",
}


def console(
    *, no_color: bool = False, width: int | None = None, stderr: bool = False
) -> Console:
    return Console(
        no_color=no_color,
        width=width,
        highlight=False,
        soft_wrap=False,
        stderr=stderr,
    )


def _difficulty(value: int) -> Text:
    filled = "●" * value + "○" * (5 - value)
    label = DIFFICULTY_LABELS.get(value, "targeted")
    return Text(f"{filled}  {value}/5 · {label}", style="magenta")


def render_simulation(simulation: Simulation, profile: Profile, out: Console) -> None:
    header = Table.grid(padding=(0, 2))
    header.add_column(style="bold cyan", justify="right")
    header.add_column()
    header.add_row("Persona", profile.name)
    header.add_row("Role", f"{profile.role} · {profile.company}")
    header.add_row("Style", profile.communication_style)
    header.add_row("Difficulty", _difficulty(simulation.difficulty))
    if simulation.objective:
        header.add_row("Objective", simulation.objective)

    out.print(
        Panel(
            header,
            title="[bold]Simulation[/bold]",
            subtitle=f"[dim]{profile.name}[/dim]",
            border_style="cyan",
            expand=False,
        )
    )

    out.print(Rule("[bold]Pretext narrative[/bold]", style="cyan"))
    out.print(Markdown(simulation.pretext))

    message_body: list[object] = []
    if simulation.subject_line:
        message_body.append(Text(f"Subject: {simulation.subject_line}", style="bold"))
        message_body.append(Text(""))
    message_body.append(Markdown(simulation.opening_message))
    out.print(
        Panel(
            Group(*message_body),
            title="[bold]Opening message[/bold]",
            border_style="green",
            expand=False,
        )
    )

    out.print(Rule("[bold]Escalation path[/bold]", style="cyan"))
    steps = Table(show_header=True, header_style="bold cyan", expand=True, box=None)
    steps.add_column("#", width=3, justify="right")
    steps.add_column("Channel", width=11)
    steps.add_column("Action", ratio=3)
    steps.add_column("Goal", ratio=2)
    for step in simulation.escalation_path:
        steps.add_row(
            str(step.stage),
            Text(step.channel.value, style="yellow"),
            Text(step.action),
            Text(step.goal, style="dim"),
        )
        if step.artifact:
            steps.add_row("", "", Text(f"↳ {step.artifact}", style="dim italic"), "")
    out.print(steps)

    out.print(Rule("[bold]Red flags for defenders[/bold]", style="cyan"))
    for index, flag in enumerate(simulation.red_flags, start=1):
        out.print(
            Panel(
                Group(
                    Markdown(flag.why_it_matters),
                    Text(""),
                    Text(f"Defender action: {flag.defender_action}", style="bold green"),
                ),
                title=f"[bold]{index}. {flag.title}[/bold]",
                border_style="red",
                expand=False,
            )
        )

    out.print(Rule(style="dim"))
    out.print(Text(DISCLAIMER, style="dim italic"))


def render_settings(settings: Settings, out: Console) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold cyan", justify="right")
    table.add_column()
    table.add_row("Endpoint", settings.endpoint)
    table.add_row("Model", settings.model)
    table.add_row("Key", "set" if settings.api_key else "[red]missing[/red]")
    table.add_row("Temperature", f"{settings.temperature:g}")
    table.add_row("Max tokens", str(settings.max_tokens))
    table.add_row("Timeout", f"{settings.timeout:g}s")
    table.add_row("Retries", str(settings.retries))
    if settings.seed is not None:
        table.add_row("Seed", str(settings.seed))
    out.print(
        Panel(
            table,
            title="[bold]Resolved configuration[/bold]",
            border_style="cyan",
            expand=False,
        )
    )


def render_profile(profile: Profile, out: Console) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold cyan", justify="right")
    table.add_column()
    for label, value in (
        ("Name", profile.name),
        ("Role", profile.role),
        ("Company", profile.company),
        ("Style", profile.communication_style),
        ("Department", profile.department),
        ("Tenure", profile.tenure),
        ("Reports to", profile.reports_to),
        ("Systems", ", ".join(profile.systems) or None),
        ("Notes", profile.notes),
    ):
        if value:
            table.add_row(label, value)
    out.print(Panel(table, title="[bold]Profile OK[/bold]", border_style="green", expand=False))


def to_markdown(simulation: Simulation, profile: Profile) -> str:
    lines = [
        f"# Social-engineering simulation: {profile.name}",
        "",
        f"- **Role:** {profile.role} at {profile.company}",
        f"- **Communication style:** {profile.communication_style}",
        f"- **Difficulty:** {simulation.difficulty}/5",
    ]
    if simulation.objective:
        lines.append(f"- **Objective:** {simulation.objective}")
    lines += ["", "## Pretext narrative", "", simulation.pretext, ""]
    lines += ["## Opening message", ""]
    if simulation.subject_line:
        lines += [f"**Subject:** {simulation.subject_line}", ""]
    lines += [simulation.opening_message, "", "## Escalation path", ""]
    for step in simulation.escalation_path:
        lines.append(
            f"{step.stage}. **{step.channel.value}** · {step.action} "
            f"_(goal: {step.goal})_"
        )
        if step.artifact:
            lines.append(f"   - Artifact: {step.artifact}")
    lines += ["", "## Red flags for defenders", ""]
    for index, flag in enumerate(simulation.red_flags, start=1):
        lines += [
            f"{index}. **{flag.title}**",
            f"   - Why it matters: {flag.why_it_matters}",
            f"   - Defender action: {flag.defender_action}",
        ]
    lines += ["", "---", "", f"_{DISCLAIMER}_", ""]
    return "\n".join(lines)


def to_json(simulation: Simulation, profile: Profile) -> str:
    payload = {
        "profile": profile.model_dump(mode="json"),
        "simulation": simulation.model_dump(mode="json"),
        "disclaimer": DISCLAIMER,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def render_warnings(warnings: Iterable[str], out: Console) -> None:
    for warning in warnings:
        out.print(Text(f"! {warning}", style="yellow"))
