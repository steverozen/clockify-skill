# NEWS

All notable changes to `clockify-skill` are recorded here. Dates are in
`YYYY-MM-DD`. Project is **alpha** — expect breaking changes in any release
below 1.0.

## v0.1.2 (2026-04-20)

Make the Claude Code skill self-contained; rename the CLI to signal its
language.

- **Renamed `clockify` → `clockify.py`.** Makes it obvious from the
  filename that this is a Python script. Shebang and behavior unchanged.
  If you had a `~/.local/bin/clockify` symlink, re-point it at
  `clockify.py`.
- **Skill no longer depends on `$PATH`.** `skill.md` now instructs Claude
  to invoke the CLI by absolute path at its install location (typically
  `python3 ~/.claude/skills/clockify/clockify.py …`), so the skill works
  on any machine where the repo is symlinked into the Claude Code skills
  directory — no shell-level install required.
- **Recommended install changed.** Symlink the whole repo to
  `~/.claude/skills/clockify` (single `ln -s`) instead of symlinking just
  `skill.md`. The PATH-based install is now documented as optional, for
  interactive shell use only.
- **Version bump** to `0.1.2` in `clockify.py`, `README.md`, and `skill.md`.

## v0.1.1 (2026-04-20)

Hardening pass on the HTTP layer and the auto-stop log writer. No API or
CLI-flag changes.

- **HTTP: retry on 429.** `api()` now retries up to 3 times on HTTP 429
  "Too Many Requests", honoring the `Retry-After` response header when
  present (falls back to exponential backoff: 1 s, 2 s, 4 s). Previously
  a single burst of `clockify` calls from an agent could exit mid-task.
- **HTTP: graceful handling of non-JSON bodies.** `api()` now catches
  `json.JSONDecodeError` and prints the HTTP status plus the first 200
  bytes of the response body instead of dumping a Python traceback. Helps
  when a proxy or load balancer returns an HTML error page or 5xx.
- **Auto-stop log: atomic writes.** The markdown log append in
  `log_auto_stop_to_priorities()` now takes an exclusive `fcntl.flock`
  around the read-modify-write cycle, so concurrent `clockify start`
  calls from multiple shells can no longer lose an entry. An `OSError`
  during the write is reported as a non-fatal warning.
- **Version bump** to `0.1.1` in the CLI (`__version__`, `--version`),
  `README.md`, and `skill.md`.

## v0.1.0 (2026-04-20)

First tagged release. Marks the project as **alpha**.

- Added `__version__ = "0.1.0"` and a `--version` flag to the `clockify`
  CLI (`clockify --version` → `clockify 0.1.0 (alpha)`).
- Added an alpha-release warning to `README.md` and `skill.md` instructing
  users to verify start/stop times in the Clockify UI before trusting
  them for billing.

## Initial import (2026-04-20, commit `0c944f2`)

Untagged. First working version of the CLI and the Claude Code skill.

- `clockify` Python 3 CLI (stdlib only), subcommands `ls`, `start`,
  `stop`, `status`. Case-insensitive `fnmatch` globs for client/project
  selection; `start` requires exactly one match per glob.
- Loud auto-stop banner when `start` is called while another timer is
  running, plus optional append to a markdown log file
  (`CLOCKIFY_AUTOSTOP_LOG` / `CLOCKIFY_AUTOSTOP_HEADING`).
- `skill.md` — Claude Code skill definition wrapping the CLI for
  natural-language invocation ("start a timer for X", "stop", "what am
  I working on?", "list projects for X").
- `README.md` with install, usage, Clockify API gotchas, and contributor
  notes.
