# Running an exercise

`pretext` writes the material. This page is the part it cannot do: deciding who is
in scope, delivering the lure, and scoring what happens.

## Before you send

- **Get written authorization.** Name the target group, the window, and which
  channels the exercise may use. Voice and SMS reach people off-hours.
- **Tell the service desk.** Otherwise the first call goes to them as a suspected
  incident and the exercise derails.
- **Pick one persona per cohort**, not per person, unless the cohort is small. A
  shared lure keeps the debrief simple.
- **Check the artifacts by hand.** pretext invents domains and ticket numbers. A
  lookalike domain that resolves to a parked page, or a ticket ID from a real
  unrelated system, will confuse the debrief.
- **Send from infrastructure you own** and record the sender addresses in the
  authorization, so an alerting defender can confirm the campaign is yours.

## Choosing a persona

Choose someone whose role makes an ask plausible: payroll, accounts payable,
helpdesk, executive assistants, and new starters all do work that arrives by email
from strangers. Fill in `systems` and `tenure` honestly; the leverage in the
narrative comes from them.

Difficulty scales with how much research you claim. Use `--channel` when you want a
specific first hit, and `--extra` to pin a constraint ("no links, email only").

## Delivering

```sh
pretext generate persona.yaml --channel email -f markdown -o exercise.md
```

- Send the **opening message** as written. Rewriting it weakens the exercise for the
  model-written ones and hides the experiment for the others.
- Hold the **escalation path** back. It is your script for the follow-up calls, not
  something trainees read on day one.
- Keep the **red flags** to yourself until the debrief.
- Note the time each stage lands. Response time is the metric that matters.

## Scoring

Score quietly, per stage:

| Signal | Read |
| ------ | ---- |
| Replied without verifying | Base case. The exercise did its job. |
| Replied, then verified out of band | Good instinct, still exposed to the first ask. |
| Called the number on the contract, not the email | Full marks. |
| Forwarded to a colleague who spotted it | Half marks; the process worked, the individual did not. |

Do not punish a click in the first exercise of a series. Punish the same mistake in
the third.

## Debrief

Run it within a week while the details are fresh, and reveal the red flags one at a
time as questions: "what did the address look like?", "who would you have called?".
People remember a tell they caught themselves far longer than one they were shown.

End with what the process fixes, not what the person missed: a vendor register that
is actually consulted, a callback number on the contract, a rule that bank-detail
changes always take two parties.

## Afterwards

- Rotate anything real the exercise touched.
- File the authorization and the debrief notes.
- Feed the misses back into the profile: a persona whose lure fails completely is
  either too easy or misjudged, and the next iteration should say which.
