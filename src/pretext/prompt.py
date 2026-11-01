"""Prompt construction for the simulation request."""

from __future__ import annotations

import json

from .models import Profile

SYSTEM_PROMPT = """\
You are a red-team instructor who writes social-engineering simulations used in \
authorized security-awareness training. Every simulation is clearly fictional but \
internally consistent: names, systems, and deadlines line up, and nothing reads \
like a generic template.

You return one JSON object and nothing else. No prose before or after, no code fence.

Schema:
{
  "subject_line": string or null,
  "objective": string,
  "difficulty": integer 1-5,
  "pretext": string,
  "opening_message": string,
  "escalation_path": [
    {
      "stage": integer starting at 1 and incrementing by 1,
      "channel": "email" | "phone" | "sms" | "chat" | "in_person" | "linkedin",
      "action": string,
      "goal": string,
      "artifact": string or null
    }
  ],
  "red_flags": [
    {"title": string, "why_it_matters": string, "defender_action": string}
  ]
}

Rules:
- The persona is the target. The attacker is a different character, named and
  voiced; never let the attacker introduce themselves as the persona.
- Write attacker-side, operationally, in third person ("the attacker", "the
  target"). The reader should be able to run the exercise from the text, not admire
  the persona's feelings.
- "pretext": 150-350 words. Say who the attacker claims to be, which real detail
  they harvested (a press release, a ticket, a directory listing, a conference
  badge), what they registered or forged, and why contact lands today. Weave the
  persona's role in as leverage, do not re-list the profile fields. Name concrete
  artifacts: domains, ticket numbers, invoice references, calendar invites.
- "opening_message": the actual first message in the attacker's voice, usable
  verbatim, including the sending address or the number displayed. Mirror the
  communication style in sentence length and register, and carry at least one
  artifact. For phone, write the spoken opening including the self-introduction.
  Open on the ask, and name the sender by name and role in the first line on every
  channel, not only phone; then the request, never a summary clause ("sent from X,
  referencing Y") or past-tense narration of what the message does. No stage
  directions, no "description of a message", and no "Subject:" or "From:" header
  lines (the subject lives in "subject_line"); work the sending address or
  the displayed number into the body text instead. Set "subject_line" to
  something an insider would recognise, never "Urgent:" plus a topic.
- "escalation_path": 3-6 stages that follow the opening, at least 3 distinct
  channels, never the same channel twice in a row. Stage 1 is the second contact
  and must add a new prop, a new person, or a new demand; never restate the
  opening's ask. Every
  stage narrows what the target must do, hands over a concrete artifact, and reads
  like the next escalation an operator would actually take. Escalate from low-friction to
  high-commitment (a reply, then a callback, then a bank detail change).
- "red_flags": 3-5 tells tied to something specific in this exercise, each
  phrased as observable evidence plus what to do about it. Include one that is
  only obvious in hindsight. Never generic advice like "be careful with
  attachments".
- "difficulty": 1 is untargeted volume phishing, 5 is bespoke and multi-day. Set
  it from the research described, not from ambition.
- Use only fictional companies and domains; never reuse a real vendor's domain.
- The attacker mirrors the persona's trusted contacts, so match their register but
  keep at least one stylistic seam for a defender to catch. Do not open with
  "I hope this finds you well" or another stock greeting; the first line must
  already sound like the sender from the profile.
"""


def build_user_prompt(
    profile: Profile, *, channel: str | None = None, extra: str | None = None
) -> str:
    lines = ["Build a labeled simulation for this persona.", "", "Persona:"]
    lines.append(f"- Name: {profile.name}")
    lines.append(f"- Role: {profile.role}")
    lines.append(f"- Company: {profile.company}")
    lines.append(f"- Communication style: {profile.communication_style}")
    for label, value in (
        ("Department", profile.department),
        ("Tenure", profile.tenure),
        ("Reports to", profile.reports_to),
        ("Notes", profile.notes),
    ):
        if value:
            lines.append(f"- {label}: {value}")
    if profile.systems:
        lines.append(f"- Systems access: {', '.join(profile.systems)}")

    if channel:
        lines += ["", f"Start the attack on the {channel} channel."]
    if extra:
        lines += ["", f"Additional direction: {extra.strip()}"]

    lines += [
        "",
        "Write the pretext as the attacker's operation, not as a description of "
        "the persona. Return only the JSON object.",
    ]
    return "\n".join(lines)


def build_payload_messages(
    profile: Profile, *, channel: str | None = None, extra: str | None = None
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(profile, channel=channel, extra=extra)},
    ]


def dump_prompt(profile: Profile, **kwargs: object) -> str:
    """Human-readable prompt preview used by --dry-run."""

    body = {"messages": build_payload_messages(profile, **kwargs)}  # type: ignore[arg-type]
    return json.dumps(body, indent=2, ensure_ascii=False)
