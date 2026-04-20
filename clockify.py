#!/usr/bin/env python3
"""Clockify CLI: start / stop / ls time tracking from the terminal.

Requires env var CLOCKIFY_API_KEY.
"""

import argparse
import fcntl
import fnmatch
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

__version__ = "0.1.2"

API_BASE = "https://api.clockify.me/api/v1"
PAGE_SIZE = 200
MAX_RETRIES_429 = 3  # retries on HTTP 429; exponential backoff or Retry-After

# Optional: when a timer is auto-stopped (because `start` was called while
# another timer was running), append a warning bullet to this file under the
# heading given by CLOCKIFY_AUTOSTOP_HEADING. Unset => skip file logging
# (banner still prints to stderr).
_LOG_PATH = os.environ.get("CLOCKIFY_AUTOSTOP_LOG")
AUTOSTOP_LOG = Path(_LOG_PATH) if _LOG_PATH else None
AUTOSTOP_HEADING = os.environ.get(
    "CLOCKIFY_AUTOSTOP_HEADING", "## Quick Tasks (< 15 min)"
)

# --- ANSI colors (skip if not a TTY) ---
_USE_COLOR = sys.stderr.isatty()
def _c(code, s):
    return f"\033[{code}m{s}\033[0m" if _USE_COLOR else s
def red(s):    return _c("1;31", s)
def yellow(s): return _c("1;33", s)
def green(s):  return _c("1;32", s)
def bold(s):   return _c("1", s)


# ---------- HTTP ----------

def _api_key():
    k = os.environ.get("CLOCKIFY_API_KEY")
    if not k:
        print(red("ERROR: CLOCKIFY_API_KEY is not set."), file=sys.stderr)
        print("Get a key here (direct link — this page is hard to find!):", file=sys.stderr)
        print("  https://app.clockify.me/user/preferences#advanced", file=sys.stderr)
        print("  → Manage API keys → Generate API key (copy immediately; shown only once)", file=sys.stderr)
        print('Then: export CLOCKIFY_API_KEY="..."  (add to ~/.bashrc)', file=sys.stderr)
        sys.exit(2)
    return k


def api(method, path, body=None, query=None):
    url = API_BASE + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    payload = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=payload, method=method,
        headers={
            "X-Api-Key": _api_key(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    for attempt in range(MAX_RETRIES_429 + 1):
        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read()
                if not raw:
                    return None
                try:
                    return json.loads(raw)
                except json.JSONDecodeError as e:
                    snippet = raw[:200].decode("utf-8", errors="replace")
                    print(red(f"ERROR: non-JSON response from {method} {path}: {e}"),
                          file=sys.stderr)
                    print(f"  Response preview: {snippet!r}", file=sys.stderr)
                    sys.exit(1)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < MAX_RETRIES_429:
                retry_after = e.headers.get("Retry-After") if e.headers else None
                try:
                    wait = float(retry_after) if retry_after else 2 ** attempt
                except ValueError:
                    wait = 2 ** attempt
                print(yellow(
                    f"Rate limited (429) on {method} {path}; "
                    f"retry {attempt + 1}/{MAX_RETRIES_429} in {wait:.1f}s…"
                ), file=sys.stderr)
                time.sleep(wait)
                continue
            err_body = e.read().decode("utf-8", errors="replace")
            print(red(f"HTTP {e.code} {e.reason} on {method} {path}"), file=sys.stderr)
            print(err_body, file=sys.stderr)
            sys.exit(1)
        except urllib.error.URLError as e:
            print(red(f"Network error: {e.reason}"), file=sys.stderr)
            sys.exit(1)


def paged_get(path, query=None):
    query = dict(query or {})
    query["page-size"] = PAGE_SIZE
    out = []
    page = 1
    while True:
        query["page"] = page
        batch = api("GET", path, query=query) or []
        out.extend(batch)
        if len(batch) < PAGE_SIZE:
            return out
        page += 1


# ---------- Clockify helpers ----------

def get_user():
    return api("GET", "/user")


def list_clients(wid):
    return paged_get(f"/workspaces/{wid}/clients")


def list_projects(wid, client_id=None):
    q = {}
    if client_id:
        q["clients"] = client_id
    return paged_get(f"/workspaces/{wid}/projects", query=q)


def get_running_timer(wid, uid):
    entries = api(
        "GET", f"/workspaces/{wid}/user/{uid}/time-entries",
        query={"in-progress": "true"},
    ) or []
    return entries[0] if entries else None


def start_timer(wid, project_id, description, billable):
    body = {
        "start": _now_iso_utc(),
        "projectId": project_id,
        "description": description,
        "billable": billable,
    }
    return api("POST", f"/workspaces/{wid}/time-entries", body=body)


def stop_timer(wid, uid):
    body = {"end": _now_iso_utc()}
    return api("PATCH", f"/workspaces/{wid}/user/{uid}/time-entries", body=body)


# ---------- Time utilities ----------

def _now_iso_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso_utc(s):
    # e.g., "2026-04-20T13:15:00Z" or "...+00:00"
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _fmt_local(dt_utc):
    return dt_utc.astimezone().strftime("%Y-%m-%d %H:%M %Z")


def _fmt_duration(seconds):
    h, rem = divmod(int(seconds), 3600)
    m, _ = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m"


# ---------- Matching ----------

def glob_match(pattern, candidates, key=lambda x: x["name"]):
    p = pattern.lower()
    return [c for c in candidates if fnmatch.fnmatchcase(key(c).lower(), p)]


def require_one(pattern, matches, kind):
    if len(matches) == 1:
        return matches[0]
    if not matches:
        print(red(f"No {kind} matches glob '{pattern}'."), file=sys.stderr)
        sys.exit(1)
    print(red(f"Glob '{pattern}' is ambiguous — matched {len(matches)} {kind}s:"),
          file=sys.stderr)
    for m in matches:
        print(f"  - {m['name']}", file=sys.stderr)
    sys.exit(1)


# ---------- Auto-stop logging ----------

def log_auto_stop_to_priorities(client_name, project_name, start_utc, end_utc):
    """Insert a warning bullet about the auto-stopped timer.

    No-op unless CLOCKIFY_AUTOSTOP_LOG is set to a path that exists.
    The bullet is inserted directly after the CLOCKIFY_AUTOSTOP_HEADING line.
    """
    if AUTOSTOP_LOG is None or not AUTOSTOP_LOG.exists():
        return
    duration = _fmt_duration((end_utc - start_utc).total_seconds())
    today = datetime.now().strftime("%Y-%m-%d")
    start_local = _fmt_local(start_utc)
    end_local = _fmt_local(end_utc)
    bullet = (
        f"- ⚠️ **Verify Clockify end time** ({today}): auto-stopped timer "
        f"`{client_name} / {project_name}` — ran {duration} "
        f"(started {start_local}, stopped {end_local}). "
        f"You may have forgotten to stop it; adjust end time in Clockify UI if wrong."
    )
    # Lock + read-modify-write so concurrent `clockify start` calls don't race.
    try:
        with open(AUTOSTOP_LOG, "r+", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                text = f.read()
                if AUTOSTOP_HEADING not in text:
                    return  # heading missing — silently skip
                pattern = re.escape(AUTOSTOP_HEADING) + r"\n"
                new_text, n = re.subn(
                    pattern, AUTOSTOP_HEADING + "\n" + bullet + "\n", text, count=1
                )
                if n:
                    f.seek(0)
                    f.write(new_text)
                    f.truncate()
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except OSError as e:
        print(yellow(f"Warning: could not update autostop log {AUTOSTOP_LOG}: {e}"),
              file=sys.stderr)


# ---------- Commands ----------

def cmd_start(args):
    user = get_user()
    wid = user["activeWorkspace"]
    uid = user["id"]

    clients = list_clients(wid)
    client = require_one(args.client, glob_match(args.client, clients), "client")

    projects = list_projects(wid, client_id=client["id"])
    project = require_one(args.project, glob_match(args.project, projects), "project")

    running = get_running_timer(wid, uid)
    if running:
        # Resolve names for the running timer
        stopped = stop_timer(wid, uid)
        start_utc = _parse_iso_utc(running["timeInterval"]["start"])
        end_utc = datetime.now(timezone.utc)
        prev_proj_id = running.get("projectId")
        prev_project = next((p for p in list_projects(wid) if p["id"] == prev_proj_id), None)
        prev_project_name = prev_project["name"] if prev_project else "(none)"
        prev_client_name = "(none)"
        if prev_project and prev_project.get("clientId"):
            prev_client = next((c for c in clients if c["id"] == prev_project["clientId"]), None)
            if prev_client:
                prev_client_name = prev_client["name"]

        dur = _fmt_duration((end_utc - start_utc).total_seconds())
        banner = [
            "",
            red("╔══════════════════════════════════════════════════════════╗"),
            red("║  ⚠️  AUTO-STOPPED PREVIOUS TIMER — VERIFY END TIME!  ⚠️  ║"),
            red("╚══════════════════════════════════════════════════════════╝"),
            f"  Client:    {yellow(prev_client_name)}",
            f"  Project:   {yellow(prev_project_name)}",
            f"  Started:   {_fmt_local(start_utc)}",
            f"  Stopped:   {_fmt_local(end_utc)}   {red('← NOW')}",
            f"  Duration:  {dur}",
            "",
            yellow("  → You may have forgotten to stop this. Adjust end time in Clockify if wrong."),
            *(
                [yellow(f"  → Logged to {AUTOSTOP_LOG} ({AUTOSTOP_HEADING}).")]
                if AUTOSTOP_LOG else []
            ),
            "",
        ]
        print("\n".join(banner), file=sys.stderr)
        log_auto_stop_to_priorities(prev_client_name, prev_project_name, start_utc, end_utc)

    entry = start_timer(wid, project["id"], args.description, args.billable)
    print(green(f"Started: {client['name']} / {project['name']}"))
    print(f'  Description: "{args.description}"')
    print(f"  Billable:    {args.billable}")


def cmd_status(args):
    user = get_user()
    wid = user["activeWorkspace"]
    uid = user["id"]
    running = get_running_timer(wid, uid)
    if not running:
        print("No timer running.")
        return

    start_utc = _parse_iso_utc(running["timeInterval"]["start"])
    elapsed = _fmt_duration((datetime.now(timezone.utc) - start_utc).total_seconds())

    proj_id = running.get("projectId")
    projects = list_projects(wid)
    project = next((p for p in projects if p["id"] == proj_id), None)
    project_name = project["name"] if project else "(none)"
    client_name = "(none)"
    if project and project.get("clientId"):
        clients = list_clients(wid)
        client = next((c for c in clients if c["id"] == project["clientId"]), None)
        if client:
            client_name = client["name"]

    description = running.get("description") or "(no description)"
    billable = "yes" if running.get("billable") else "no"

    print(green("⏱  Timer running"))
    print(f"  Client:      {client_name}")
    print(f"  Project:     {project_name}")
    print(f"  Description: {description}")
    print(f"  Billable:    {billable}")
    print(f"  Started:     {_fmt_local(start_utc)}")
    print(f"  Elapsed:     {elapsed}")


def cmd_stop(args):
    user = get_user()
    wid = user["activeWorkspace"]
    uid = user["id"]
    running = get_running_timer(wid, uid)
    if not running:
        print("No timer running.")
        return
    start_utc = _parse_iso_utc(running["timeInterval"]["start"])
    stop_timer(wid, uid)
    end_utc = datetime.now(timezone.utc)

    proj_id = running.get("projectId")
    projects = list_projects(wid)
    project = next((p for p in projects if p["id"] == proj_id), None)
    project_name = project["name"] if project else "(none)"
    client_name = "(none)"
    if project and project.get("clientId"):
        clients = list_clients(wid)
        client = next((c for c in clients if c["id"] == project["clientId"]), None)
        if client:
            client_name = client["name"]

    dur = _fmt_duration((end_utc - start_utc).total_seconds())
    print(green(f"Stopped: {client_name} / {project_name} — {dur}"))


def cmd_ls(args):
    user = get_user()
    wid = user["activeWorkspace"]

    clients = list_clients(wid)
    projects = list_projects(wid)

    client_by_id = {c["id"]: c for c in clients}

    if args.client:
        matched_clients = glob_match(args.client, clients)
        matched_client_ids = {c["id"] for c in matched_clients}
        projects = [p for p in projects if p.get("clientId") in matched_client_ids]

    if args.project:
        projects = glob_match(args.project, projects)

    # Build rows
    rows = []
    for p in projects:
        client = client_by_id.get(p.get("clientId")) if p.get("clientId") else None
        rows.append((
            client["name"] if client else "(unassigned)",
            p["name"],
            "yes" if p.get("billable") else "no",
        ))

    # Also show clients with zero matching projects if --client was given and no project filter
    if args.client and not args.project:
        shown_clients = {r[0] for r in rows}
        for c in glob_match(args.client, clients):
            if c["name"] not in shown_clients:
                rows.append((c["name"], "(no projects)", "-"))

    if not rows:
        print("No matches.")
        return

    rows.sort(key=lambda r: (r[0].lower(), r[1].lower()))
    w_client = max(len("CLIENT"), max(len(r[0]) for r in rows))
    w_project = max(len("PROJECT"), max(len(r[1]) for r in rows))
    sep = "─" * (w_client + w_project + 14)
    print(bold(f"{'CLIENT':<{w_client}}  {'PROJECT':<{w_project}}  BILLABLE"))
    print(sep)
    for c, p, b in rows:
        print(f"{c:<{w_client}}  {p:<{w_project}}  {b}")


# ---------- Main ----------

def main():
    p = argparse.ArgumentParser(
        prog="clockify",
        description="Clockify time tracker — start, stop, ls (case-insensitive globs).",
    )
    p.add_argument("--version", action="version",
                   version=f"%(prog)s {__version__} (alpha)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("start", help="Start a timer on a client/project")
    s.add_argument("client", help="Client glob (case-insensitive, e.g. '*feng*')")
    s.add_argument("project", help="Project glob (case-insensitive, e.g. 'bewo*')")
    s.add_argument("--description", default="FILL ME IN LATER",
                   help="Time entry description (default: %(default)s)")
    s.add_argument("--billable", action="store_true",
                   help="Mark entry as billable (default: False)")
    s.set_defaults(fn=cmd_start)

    st = sub.add_parser("stop", help="Stop the currently running timer")
    st.set_defaults(fn=cmd_stop)

    status = sub.add_parser("status", help="Show the currently running timer")
    status.set_defaults(fn=cmd_status)

    l = sub.add_parser("ls", help="List clients and projects (optional globs)")
    l.add_argument("--client", help="Filter by client glob (case-insensitive)")
    l.add_argument("--project", help="Filter by project glob (case-insensitive)")
    l.set_defaults(fn=cmd_ls)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
