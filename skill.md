---
name: clockify
description: Clockify time tracking. Start/stop/list timers via natural language. Wraps the colocated `clockify.py` CLI; uses case-insensitive globs to match clients and projects.
version: 0.1.2
user_invocable: true
---

# Clockify Time Tracking

> **Alpha (v0.1.2).** Behavior and flags may change. Verify start/stop times
> in the Clockify UI before trusting them for billing.

## When to Use
Any time the user mentions time tracking, timers, billable time, or names a client/project in a "start working on X" / "stop" / "what's running" / "list projects" context. Examples:

- "start a timer for <client> <project>"
- "stop the timer"
- "I'm working on <project> now"
- "list projects for <client>"
- "what clients do I have matching <glob>?"

## Invoking the CLI

The `clockify.py` script ships in the same folder as this `skill.md`. **Do not rely on `$PATH`.** Invoke it by its absolute path. The canonical install location for a user-scoped skill is:

```bash
python3 ~/.claude/skills/clockify/clockify.py <subcommand> [args]
```

If installed elsewhere (e.g. a project-scoped `.claude/skills/clockify/`, or a different user-level path), substitute that directory. The script requires Python ≥ 3.8 (stdlib only, no `pip install`) and the env var `CLOCKIFY_API_KEY`.

Throughout this skill, examples are written with `clockify` as shorthand for the full `python3 …/clockify.py` invocation — substitute the real path when running.

## CLI Reference

```bash
clockify ls [--client GLOB] [--project GLOB]
clockify start CLIENT_GLOB PROJECT_GLOB [--description TEXT] [--billable]
clockify stop
clockify status
clockify --version
```

- **Globs are case-insensitive fnmatch** (`*`, `?`, `[abc]`). Quote them in shell: `'*feng*'`.
- **`start` requires exactly one match** per glob. If 0 or >1 matches, it errors with the list.
- **`--description`** defaults to `"FILL ME IN LATER"`. **`--billable`** defaults to False.
- API key lives in the env var `CLOCKIFY_API_KEY`.

## Process

### Starting a timer

When the user says "start a timer on <client> <project>":

1. **Run `clockify start <client-glob> <project-glob>`** with whatever hints the user gave.
   - Use loose globs if the user was imprecise: `*feng*`, `*obgyn*`, etc.
   - If the user mentioned a description, pass `--description "<text>"`.
   - If the user mentioned billable/non-billable, pass `--billable` accordingly (defaults to not billable).
2. **If the command errors with "No match" or "ambiguous"**:
   - Run `clockify ls --client <glob>` or `clockify ls --project <glob>` to show options.
   - Ask the user which one they meant.
3. **If the auto-stop warning banner fires**:
   - **Read it carefully** — the user likely forgot to stop a previous timer.
   - Show the banner content prominently in your reply.
   - Remind them they may need to adjust the end time in the Clockify UI.

### Checking current status

When the user asks "what am I working on?" / "is anything running?" / "status":

1. Run `clockify status`.
2. Report the client, project, description, and elapsed time. If nothing running, say so.

### Stopping a timer

When the user says "stop" / "stop the timer" / "I'm done":

1. Run `clockify stop`.
2. Report the duration.

### Listing / querying

When the user asks "what projects do I have for X" / "list X projects" / etc:

1. Run `clockify ls` with appropriate `--client` / `--project` glob flags.
2. Format the output for readability. Group by client if it's a long list.

### Switching timers

When the user says "switch to <client> <project>" or starts a new timer while another is running:

- Just run `clockify start`. The CLI auto-stops the previous timer and prints a loud warning banner.
- **Surface the warning to the user immediately** — include the banner content in your reply so they see it.

## Common Patterns

Remember: `clockify` below is shorthand for `python3 ~/.claude/skills/clockify/clockify.py` (or wherever the skill is installed).

| User says | Run |
|---|---|
| "start obgyn feng" | `clockify start '*obgyn*' '*feng*'` |
| "start sgt luftig, billable" | `clockify start '*sgt*' '*luftig*' --billable` |
| "start client proj, with description X" | `clockify start <client> <proj> --description "X"` |
| "stop" | `clockify stop` |
| "what am I working on?" | `clockify status` |
| "what clients do I have with feng?" | `clockify ls --client '*feng*'` |
| "list obgyn projects" | `clockify ls --client '*obgyn*'` |
| "show all projects" | `clockify ls` |

## Tone

Terse. Report what happened. If auto-stop fired, be **loud and specific** about which timer was stopped and when — the end time is probably wrong and needs manual correction in the Clockify UI.

## Notes

- Never expose `CLOCKIFY_API_KEY` in output, logs, or commits.
- If `clockify start X Y` fails because no such project exists, don't silently create anything — tell the user and let them create the project in the Clockify UI.
