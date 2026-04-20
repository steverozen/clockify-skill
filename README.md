# clockify-skill

**Version: v0.1.0 — alpha release.** Expect rough edges, breaking changes,
and bugs. Test against a throwaway Clockify workspace before trusting it
with billable time. Please file issues.

Terminal CLI for [Clockify](https://clockify.me) time tracking — plus a
[Claude Code](https://claude.com/claude-code) skill that wraps it so you can
start, stop, and query timers via natural language.

- **`clockify`** — Python 3 CLI (stdlib only, no `pip install`). Start / stop
  / list timers with case-insensitive globs.
- **`skill.md`** — Claude Code skill definition. Drop into
  `~/.claude/skills/clockify/` and Claude will invoke the CLI for you when
  you say "start a timer for X" / "stop" / "what am I working on?".

## Why

Clockify's web and desktop apps are fine, but:
- Context switching out of the terminal is friction.
- Forgotten-timer recovery is tedious (you have to scroll back and edit end
  times manually).
- Starting a new timer should auto-stop the old one **and warn you loudly**,
  not silently — because the old end time is almost certainly wrong.

This CLI does all three.

## Features

- `clockify ls [--client GLOB] [--project GLOB]` — list clients and projects
  filtered by case-insensitive glob
- `clockify start CLIENT PROJECT [--description TEXT] [--billable]` — start a
  timer; both args are globs and must each match exactly one entry
- `clockify stop` — stop the running timer; prints duration
- `clockify status` — show the currently running timer (client, project,
  description, start time, elapsed)
- **Loud auto-stop warning**: if a timer is already running when you call
  `start`, it's stopped with a bright red banner reminding you to check the
  end time. Optionally logs the warning to a markdown file.

## Install

```bash
# 1. Clone
git clone git@github.com:steverozen/clockify-skill.git ~/github/clockify-skill

# 2. Put CLI on PATH
ln -sf ~/github/clockify-skill/clockify ~/.local/bin/clockify

# 3. Set API key (get it at https://app.clockify.me/user/preferences#advanced
#    → Manage API keys → Generate API key; copy immediately — shown only once)
export CLOCKIFY_API_KEY="..."
echo 'export CLOCKIFY_API_KEY="..."' >> ~/.bashrc   # or source a ~/.secrets file

# 4. Test
clockify ls
```

## Use

```bash
# list everything
clockify ls

# glob filter (case-insensitive fnmatch)
clockify ls --client '*feng*'
clockify ls --project 'obg*'
clockify ls --client sgt-core --project '*rna*'

# start a timer — both args are globs that must match exactly one entry
clockify start '*obgyn*' 'bewo*'
clockify start obgyn bewo --description "scoping call" --billable

# check current status
clockify status

# stop
clockify stop
```

### Switching timers (the loud auto-stop)

```bash
clockify start obgyn feng
# ... time passes, you forget to stop ...
clockify start sgt-core indel-paper
```

Output on the second `start`:

```
╔══════════════════════════════════════════════════════════╗
║  ⚠️  AUTO-STOPPED PREVIOUS TIMER — VERIFY END TIME!  ⚠️  ║
╚══════════════════════════════════════════════════════════╝
  Client:    obgyn
  Project:   feng
  Started:   2026-04-20 07:23 EDT
  Stopped:   2026-04-20 09:15 EDT   ← NOW
  Duration:  1h 52m

  → You may have forgotten to stop this. Adjust end time in Clockify if wrong.

Started: sgt-core / indel-paper
```

The banner reminds you the end time of the old timer is "when you ran the
new `start` command" — which is probably NOT when you actually stopped
working. Go fix it in the Clockify UI.

## Optional: log auto-stops to a markdown file

Set `CLOCKIFY_AUTOSTOP_LOG` to a markdown file path. When an auto-stop fires,
the CLI appends a bullet under `## Quick Tasks (< 15 min)` (or whatever
heading you set via `CLOCKIFY_AUTOSTOP_HEADING`) so you see it in your
daily/weekly review and remember to fix the end time.

```bash
export CLOCKIFY_AUTOSTOP_LOG="$HOME/notes/priorities.md"
export CLOCKIFY_AUTOSTOP_HEADING="## Quick Tasks"   # optional override
```

If `CLOCKIFY_AUTOSTOP_LOG` is unset, the banner still prints but nothing is
written to disk.

## Claude Code skill

The `skill.md` file is a Claude Code skill definition. To install:

```bash
mkdir -p ~/.claude/skills/clockify
ln -sf ~/github/clockify-skill/skill.md ~/.claude/skills/clockify/skill.md
```

Then in a Claude Code session:

- "start a timer for obgyn feng"
- "what am I working on?"
- "stop"
- "list obgyn projects"

Claude will run the right `clockify` command, surface the result, and
prominently warn you about any auto-stopped timers.

## Clockify API gotchas

Documented for your sanity (and future Claude's):

- **Deleting a client requires archiving it first.** `DELETE /clients/{id}`
  on an active client returns `HTTP 400 {"message":"Cannot delete an active
  client","code":501}`. The wording is misleading — "active" means "not
  archived". Do: `PUT /clients/{id} {"archived": true}` then `DELETE`.

- **Orphan clients (zero projects) are hidden from project-centric views**
  like `clockify ls`. Hit `GET /clients` directly to find them.

- **Time entries attach to projects, not clients.** A time entry has a
  `projectId` but no `clientId`; the client is inherited via the project.
  "Move all time from client X to client Y" really means moving entries
  between projects.

- **Only one timer can run at a time.** Calling `POST /time-entries` while
  one is running doesn't always auto-stop the old one server-side — so this
  CLI explicitly stops first, surfaces the warning, then starts the new one.

- **Paginate at `page-size=200`** (server-side max).

- **Timestamps are ISO 8601 UTC** (`2026-04-20T13:15:00Z`). The CLI converts
  to local time for display.

## Dependencies

- Python ≥ 3.8 (uses `argparse`, `urllib`, `fnmatch`, `json`, `datetime`,
  `pathlib`, `re` — all stdlib)
- Clockify account + personal API key

That's it. No `pip install`.

## License

[MIT](LICENSE) — use it however you like.

## Contributing

PRs welcome. Keep it stdlib-only — no dependencies. Keep each subcommand
self-contained. Don't add features that force a config file.

## Author

Built by [Steven G. Rozen](https://github.com/steverozen) with help from
Claude (Anthropic).
