# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Two artifacts ship from one repo:

1. **`clockify`** — a single-file Python 3 CLI for Clockify time tracking (stdlib only, executable script).
2. **`skill.md`** — a Claude Code skill that teaches Claude to invoke the CLI from natural-language prompts.

There is no build system, no package, no test suite. Edits to the CLI are exercised by running it directly.

## Running / smoke-testing

```bash
export CLOCKIFY_API_KEY="..."           # required; personal API key from Clockify
./clockify ls                           # hits live API; cheapest end-to-end check
./clockify ls --client '*foo*'          # glob filter
./clockify status
./clockify start '<client>' '<project>' [--description "..."] [--billable]
./clockify stop
```

Every command calls the live Clockify API — there are no mocks or fixtures. When changing request/response handling, test against the real service with a throwaway client/project.

Optional env vars:
- `CLOCKIFY_AUTOSTOP_LOG` — markdown file path; auto-stop warnings get appended under a heading
- `CLOCKIFY_AUTOSTOP_HEADING` — heading under which the bullet is inserted (default `## Quick Tasks (< 15 min)`)

## Architecture

The CLI is one file (`clockify`, ~410 lines) organized into layered sections:

- **HTTP layer** — `api()` (single request) and `paged_get()` (iterates at `page-size=200`, the server max). All subcommands go through these.
- **Clockify helpers** — thin wrappers around specific endpoints: `get_user`, `list_clients`, `list_projects`, `get_running_timer`, `start_timer`, `stop_timer`. Workspace id (`wid`) and user id (`uid`) come from `/user`.
- **Matching** — `glob_match()` uses case-insensitive `fnmatch` against `name`; `require_one()` enforces exactly-one-match semantics for `start` (errors listing all matches if ambiguous).
- **Commands** — `cmd_start`, `cmd_stop`, `cmd_status`, `cmd_ls`. Each command re-fetches clients/projects; there is no caching by design (keeps each subcommand self-contained).
- **Auto-stop flow** (in `cmd_start`): if a timer is already running, stop it first, print a red banner to **stderr** (so pipes don't eat it), optionally append to the markdown log via `log_auto_stop_to_priorities()`, then start the new timer. The banner exists because the server-side end time equals "now" — which is almost always wrong — so the user must be reminded to fix it in the UI.
- **ANSI color** is auto-disabled when stderr isn't a TTY (`_USE_COLOR`).

## Clockify API gotchas (baked into the code — don't regress)

- **Only one timer can run per user.** Starting a new one while another runs does not reliably auto-stop server-side; the CLI explicitly stops first, hence the banner.
- **Time entries belong to projects, not clients.** The client name is looked up via `project.clientId`.
- **Deleting a client requires `PUT {archived: true}` first**, then `DELETE`. "Cannot delete an active client" means "not archived", not "has running timer". (Not currently implemented in the CLI but documented in README.)
- **Paginate at `page-size=200`** — server-side maximum.
- **Timestamps are ISO 8601 UTC** (`...Z`); `_parse_iso_utc` / `_fmt_local` convert for display.

## Constraints to preserve

These are load-bearing project decisions — don't casually break them:

- **Stdlib only.** No `pip install`, no `requirements.txt`. If a change seems to need a library, push back.
- **No config file.** All config is CLI args or env vars.
- **Each subcommand is self-contained** — re-fetch rather than thread shared state.
- **The auto-stop banner goes to stderr and must stay loud** (red, boxed, with explicit "← NOW" marker). Its whole purpose is to make forgotten timers impossible to miss.
- **Never print or log `CLOCKIFY_API_KEY`.**
- Keep `skill.md` in sync with the CLI surface: new flags / subcommands need a row in its "Common Patterns" table.
