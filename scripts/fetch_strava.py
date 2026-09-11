#!/usr/bin/env python3
"""Fetch Strava activities and emit the running and push-up habit files.

Produces ``running.json`` — miles per day from Run / TrailRun / VirtualRun
activities — and ``pushups.json`` — reps per day from the "Workout" entries the
Puuush app posts.

The rep count is only in the activity **description**, and the activity list
endpoint does not return one, so every push-up session costs an extra detail
call. ``build_pushup_days`` rations and caches those; read it before changing
anything here.

Stretching deliberately does *not* come from here. Strava's other "Workout"
entries are strength sessions, not stretching; the stretching habit is sourced
from the Bend app via ``import_health.py`` instead.

Usage:
    python scripts/fetch_strava.py --auth      # one-time: authorize the app
    python scripts/fetch_strava.py             # normal run (last 730 days)
    python scripts/fetch_strava.py --days 30   # shorter window
    python scripts/fetch_strava.py --limit 5   # quick test

Credentials come from the environment or ``scripts/.env``:
``STRAVA_CLIENT_ID``, ``STRAVA_CLIENT_SECRET``, ``STRAVA_REFRESH_TOKEN``.

This talks to the REST API over ``urllib`` rather than using ``stravalib`` so
the nightly GitHub Action needs no pip install and cannot break on an upstream
release. Strava reports SI units: distance in metres, times in seconds; the
habit file records miles, so distances are converted on the way out.
"""

from __future__ import annotations

import argparse
import datetime as dt
import http.server
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from typing import Any

import habits_common as hc

TOKEN_URL = "https://www.strava.com/oauth/token"
AUTH_URL = "https://www.strava.com/oauth/authorize"
ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"
ACTIVITY_URL = "https://www.strava.com/api/v3/activities/{}"

# The authorization code comes back as a query parameter on this URL, so
# --auth briefly serves it locally and reads the code directly. Relying on the
# browser to display an unreachable URL does not work: Safari and Chrome both
# replace a failed navigation with a search page, discarding the code.
#
# The port is arbitrary but must be free and above 1024 (binding 80 needs
# root). Strava validates only the host of the redirect, so the Authorization
# Callback Domain stays plain `localhost` regardless of the port.
CALLBACK_PORT = 8721
REDIRECT_URI = f"http://localhost:{CALLBACK_PORT}/exchange_token"
SCOPE = "activity:read_all"

# Without this scope the token can refresh but not list activities, which
# surfaces later as a confusing 401.
REQUIRED_SCOPE = "activity:read"

RUN_TYPES = {"Run", "TrailRun", "VirtualRun"}

# Push-ups reach Strava from the Puuush app as plain "Workout" activities, so
# the type alone cannot pick them out — an Apple Watch strength circuit lands in
# exactly the same bucket. The name is what separates them.
PUSHUP_TYPES = {"Workout"}
PUSHUP_NAME = re.compile(r"push[\s_-]?ups?", re.IGNORECASE)

# Puuush writes the count into the description as prose:
#
#     Total Reps: 15
#     Average Time per Push-Up: 1.53s
#
# There is no structured field to read instead — Strava's strength-workout
# breakdown returns an empty set list for these — so the description is it.
PUSHUP_REPS = re.compile(r"total\s+reps:\s*([\d,]+)", re.IGNORECASE)

# Strava allows 200 requests per 15 minutes. The activity list costs a couple of
# pages; the rest is available for detail calls, and this leaves headroom.
DETAIL_BUDGET = 150

METRES_PER_MILE = 1609.344

PER_PAGE = 200


def api_post(url: str, data: dict[str, str]) -> dict:
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30, context=hc.ssl_context()) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        raise SystemExit(f"Strava {exc.code} from {url}: {detail}") from exc


def api_get(url: str, token: str, params: dict[str, str] | None = None) -> Any:
    full = f"{url}?{urllib.parse.urlencode(params)}" if params else url
    req = urllib.request.Request(full, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30, context=hc.ssl_context()) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        if exc.code == 429:
            raise SystemExit("Strava rate limit hit (200/15min). Try again shortly.") from exc
        if exc.code == 401 and "activity:read_permission" in detail:
            # The token refreshed fine but cannot read activities. Nearly always
            # means the refresh token was copied off the Strava API settings
            # page, which issues one scoped to `read` only.
            raise SystemExit(
                "Strava rejected the token for lacking activity:read permission.\n"
                "\n"
                "  The refresh token shown on strava.com/settings/api only carries the\n"
                "  `read` scope, which cannot list activities. You need one from the\n"
                "  OAuth flow:\n"
                "\n"
                "      python scripts/fetch_strava.py --auth\n"
                "\n"
                "  On Strava's authorization screen, leave the private-activity box\n"
                "  ticked — unticking it drops the scope this needs. Then copy the new\n"
                "  token out of scripts/.env into the STRAVA_REFRESH_TOKEN secret."
            ) from exc
        raise SystemExit(f"Strava {exc.code} from {url}: {detail}") from exc


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    """Catches Strava's one redirect back and stashes the query parameters."""

    params: dict[str, list[str]] = {}

    def do_GET(self) -> None:
        query = urllib.parse.urlparse(self.path).query
        found = urllib.parse.parse_qs(query)
        # Browsers also request /favicon.ico; only the redirect carries these.
        if "code" in found or "error" in found:
            _CallbackHandler.params = found
        ok = "code" in found
        body = (
            "<h2>Authorized.</h2><p>You can close this tab and return to the terminal.</p>"
            if ok else
            "<h2>Authorization failed.</h2><p>Check the terminal for details.</p>"
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        pass  # keep the server silent; the script does its own reporting


def await_callback(timeout: int = 300) -> dict[str, list[str]]:
    """Serve on the callback port until Strava redirects back."""
    _CallbackHandler.params = {}
    try:
        server = http.server.HTTPServer(("127.0.0.1", CALLBACK_PORT), _CallbackHandler)
    except OSError as exc:
        raise SystemExit(
            f"could not listen on port {CALLBACK_PORT} ({exc}).\n"
            f"  Something else is using it. Free the port and retry, or use\n"
            f"  --manual to paste the code by hand."
        ) from exc

    # Keep serving until the redirect lands or the overall deadline passes.
    # A single handle_request() is not enough: browsers fetch /favicon.ico
    # alongside the page, and that request would otherwise consume the one
    # served request and end the wait before Strava's redirect arrives.
    deadline = time.monotonic() + timeout
    with server:
        while not _CallbackHandler.params:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            server.timeout = remaining
            server.handle_request()
    return _CallbackHandler.params


def interactive_auth(manual: bool = False) -> None:
    """Walk the one-time authorization-code exchange and save the tokens."""
    client_id = hc.env("STRAVA_CLIENT_ID")
    client_secret = hc.env("STRAVA_CLIENT_SECRET")
    query = urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        # `force` so re-running always re-prompts; with `auto` Strava silently
        # reuses a previous grant, which would quietly keep a narrower scope.
        "approval_prompt": "force",
        "scope": SCOPE,
    })
    url = f"{AUTH_URL}?{query}"

    print("\nAuthorize this app with Strava:\n")
    print(f"   {url}\n")
    print("On Strava's screen, leave every box ticked — including")
    print("\"View data about your private activities\". Unticking that box is")
    print("what produces an activity:read_permission error later.\n")
    print("If Strava shows an error instead of its authorization screen, the")
    print("Authorization Callback Domain on strava.com/settings/api is not set")
    print(f"to exactly: localhost\n")

    if manual:
        print("Paste the whole URL you land on (or just the code):\n")
        raw = input("> ").strip()
        if not raw:
            raise SystemExit("nothing supplied")
        code = raw
        if "code=" in raw:
            code = urllib.parse.parse_qs(urllib.parse.urlparse(raw).query).get("code", [""])[0]
        if not code:
            raise SystemExit(f"no code found in: {raw[:120]}")
        granted = ""
    else:
        try:
            webbrowser.open(url)
        except Exception:
            pass  # the URL is printed above; opening it is a convenience
        print(f"Waiting for Strava to redirect back to port {CALLBACK_PORT}...")
        params = await_callback()
        if not params:
            raise SystemExit(
                "timed out waiting for the redirect.\n"
                "  If you did authorize, your browser may have blocked the\n"
                "  localhost callback — rerun with --manual and paste the URL."
            )
        if "error" in params:
            raise SystemExit(
                f"Strava returned an error: {params['error'][0]}.\n"
                "  `access_denied` means the authorization was declined or a\n"
                "  permission box was unticked. Rerun and accept all of them."
            )
        code = params["code"][0]
        granted = ",".join(params.get("scope", []))
        print(f"Received authorization code. Granted scope: {granted or 'unreported'}")

    if granted and REQUIRED_SCOPE not in granted:
        raise SystemExit(
            f"Strava granted only '{granted}', which cannot list activities.\n"
            f"  Rerun --auth and leave the private-activity box ticked."
        )

    tokens = api_post(TOKEN_URL, {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
    })
    refresh = tokens.get("refresh_token")
    if not refresh:
        raise SystemExit(f"unexpected token response: {tokens}")
    hc.update_env_file({"STRAVA_REFRESH_TOKEN": refresh})
    print(f"\nSaved STRAVA_REFRESH_TOKEN to {hc.ENV_PATH}.")
    print("\nNow store it as a repository secret:\n")
    print("    gh secret set STRAVA_REFRESH_TOKEN < <(grep STRAVA_REFRESH_TOKEN "
          "scripts/.env | cut -d= -f2)\n")


def access_token() -> str:
    """Exchange the stored refresh token for an access token.

    Strava may hand back a rotated refresh token; persisting it immediately is
    what keeps the next run from failing with an invalid grant.
    """
    refresh = hc.env("STRAVA_REFRESH_TOKEN")
    tokens = api_post(TOKEN_URL, {
        "client_id": hc.env("STRAVA_CLIENT_ID"),
        "client_secret": hc.env("STRAVA_CLIENT_SECRET"),
        "refresh_token": refresh,
        "grant_type": "refresh_token",
    })
    rotated = tokens.get("refresh_token")
    if rotated and rotated != refresh:
        hc.log("Strava rotated the refresh token; persisting the new value")
        hc.update_env_file({"STRAVA_REFRESH_TOKEN": rotated})
        # In CI the new token has to reach the secret store, but printing it
        # would leak it into the workflow log — GitHub only masks secrets it
        # already knows. Write it to a file the workflow reads instead.
        sink = os.environ.get("STRAVA_TOKEN_SINK")
        if sink:
            with open(sink, "w", encoding="utf-8") as fh:
                fh.write(rotated)
            os.chmod(sink, 0o600)
            hc.log(f"rotated token written to {sink}")
    token = tokens.get("access_token")
    if not token:
        raise SystemExit(f"no access_token in response: {tokens}")
    return token


def fetch_activities(token: str, after: dt.date, limit: int | None) -> list[dict]:
    after_ts = int(dt.datetime.combine(after, dt.time.min).timestamp())
    out: list[dict] = []
    page = 1
    while True:
        batch = api_get(ACTIVITIES_URL, token, {
            "after": str(after_ts),
            "page": str(page),
            "per_page": str(PER_PAGE),
        })
        if not batch:
            break
        out.extend(batch)
        hc.log(f"  page {page}: {len(batch)} activities (total {len(out)})")
        if limit and len(out) >= limit:
            return out[:limit]
        if len(batch) < PER_PAGE:
            break
        page += 1
    return out


def activity_type(act: dict) -> str:
    """Prefer sport_type; Strava's older `type` field collapses several sports."""
    return act.get("sport_type") or act.get("type") or ""


def activity_day(act: dict) -> str:
    """File the activity under its local start date, not UTC.

    A 7pm run in Boston is a 23:00 or 00:00 UTC timestamp — using UTC would
    scatter evening workouts onto the following day.
    """
    stamp = act.get("start_date_local") or act.get("start_date") or ""
    return stamp[:10]


def build_days(acts: list[dict], types: set[str]) -> dict[str, dict]:
    """Aggregate matching activities into per-day habit records."""
    buckets: dict[str, dict[str, float]] = {}
    for act in acts:
        if activity_type(act) not in types:
            continue
        key = activity_day(act)
        if not key:
            continue
        acc = buckets.setdefault(key, {"distance_m": 0.0, "moving_time_s": 0.0, "count": 0})
        acc["distance_m"] += float(act.get("distance") or 0)
        acc["moving_time_s"] += float(act.get("moving_time") or 0)
        acc["count"] += 1

    days: dict[str, dict] = {}
    for key, acc in buckets.items():
        days[key] = hc.day(
            acc["distance_m"] / METRES_PER_MILE,
            moving_time_s=int(acc["moving_time_s"]),
            distance_m=int(acc["distance_m"]),
            count=int(acc["count"]),
        )
    return days


def activity_reps(token: str, act: dict) -> int | None:
    """Read one session's rep count out of its description.

    Costs an API call. ``/athlete/activities`` returns a summary that carries no
    ``description`` key at all, so the detail endpoint is the only way to it.
    """
    detail = api_get(ACTIVITY_URL.format(act.get("id")), token)
    found = PUSHUP_REPS.search(detail.get("description") or "")
    return int(found.group(1).replace(",", "")) if found else None


def build_pushup_days(
    token: str,
    acts: list[dict],
    existing: dict[str, dict],
    budget: int = DETAIL_BUDGET,
) -> dict[str, dict]:
    """Aggregate push-up sessions into per-day rep totals.

    A detail call per session would eventually outgrow Strava's rate limit, so a
    day the file already records with the same number of sessions is reused
    untouched and never read again. Cost then tracks what changed rather than
    how long the history is — which is what makes the two-year default window
    affordable, and why the merge in ``write_habit`` is leaned on rather than
    worked around. A day whose session count moved is re-read in full, so a
    session added or deleted after the fact still corrects itself.

    Days resolve newest first, so if the budget does run out it is the oldest
    unresolved day that waits for the next run rather than today's.
    """
    by_day: dict[str, list[dict]] = {}
    for act in acts:
        if activity_type(act) not in PUSHUP_TYPES:
            continue
        if not PUSHUP_NAME.search(act.get("name") or ""):
            continue
        key = activity_day(act)
        if key:
            by_day.setdefault(key, []).append(act)

    days: dict[str, dict] = {}
    spent = 0
    for key in sorted(by_day, reverse=True):
        group = by_day[key]
        prior = existing.get(key)
        if prior and int((prior.get("extra") or {}).get("count") or 1) == len(group):
            days[key] = prior
            continue
        if spent + len(group) > budget:
            hc.log(f"  detail budget of {budget} spent; {key} and earlier wait for the next run")
            break
        reps = 0
        for act in group:
            spent += 1
            got = activity_reps(token, act)
            if got is None:
                # Logged by hand, or a Puuush release that reworded the summary.
                # Warn rather than write a zero, which the page would render as
                # an ordinary rest day.
                hc.log(f"  warning: no 'Total Reps' in the description of activity "
                       f"{act.get('id')} on {key}")
                continue
            reps += got
        if reps:
            days[key] = hc.day(reps, count=len(group))
    if spent:
        hc.log(f"  read {spent} push-up description{'' if spent == 1 else 's'}")
    return days


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--auth", action="store_true", help="run the one-time OAuth flow and exit")
    ap.add_argument("--manual", action="store_true",
                    help="with --auth, paste the redirect URL instead of catching it locally")
    ap.add_argument("--days", type=int, default=730, help="how far back to fetch (default: 730)")
    ap.add_argument("--limit", type=int, help="stop after N activities (for testing)")
    ap.add_argument("--out-dir", default=hc.DATA_DIR, help="habit JSON directory")
    ap.add_argument("--no-merge", action="store_true", help="rebuild the files instead of merging")
    ap.add_argument("--run-types", default=",".join(sorted(RUN_TYPES)))
    ap.add_argument("--detail-budget", type=int, default=DETAIL_BUDGET,
                    help="cap on push-up detail calls per run (Strava allows 200/15min)")
    args = ap.parse_args(argv)

    if args.auth:
        interactive_auth(manual=args.manual)
        return 0

    after = hc.days_ago(args.days)
    hc.log(f"fetching Strava activities since {after}")
    token = access_token()
    acts = fetch_activities(token, after, args.limit)
    hc.log(f"fetched {len(acts)} activities")

    run_types = {t.strip() for t in args.run_types.split(",") if t.strip()}
    hc.write_habit(
        "running", "Running", "Strava", "mi",
        build_days(acts, run_types),
        merge=not args.no_merge, data_dir=args.out_dir,
    )

    # Written second, and reading its own file first: the running data is safely
    # on disk before any detail call gets the chance to fail, and --no-merge
    # means "rebuild", so it has to discard the cache too or nothing is re-read.
    prior = {} if args.no_merge else (hc.load_habit("pushups", args.out_dir).get("days") or {})
    hc.write_habit(
        "pushups", "Push-ups", "Strava", "reps",
        build_pushup_days(token, acts, prior, args.detail_budget),
        merge=not args.no_merge, data_dir=args.out_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
