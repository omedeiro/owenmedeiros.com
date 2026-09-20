#!/usr/bin/env python3
"""Merge Bend sessions pushed off the phone by an iOS Shortcut.

Bend syncs its sessions into Apple Health, and Apple Health is where the trail
goes cold: HealthKit is on-device only, there is no web API, and Health does
not reach the Mac either — it moves between devices through CloudKit's private
database, not as files. So a session can only leave the phone if something on
the phone pushes it. A scheduled Shortcut is that something, and it has two
places to push to:

* **GitHub** — the Shortcut POSTs a ``repository_dispatch`` and
  ``.github/workflows/stretching.yml`` runs this script with ``--payload-file``.
  Nothing else has to be awake, so this is the route that actually updates
  every day.
* **iCloud Drive** — the Shortcut writes a file into ``habits/stretching/``,
  which mirrors to ``~/Library/Mobile Documents/com~apple~CloudDocs/`` and
  needs no Full Disk Access to read. The nightly LaunchAgent picks it up, so it
  only runs when the Mac is on. Kept as a fallback, exactly as
  ``import_shortcut_sleep.py`` does for sleep.

Both routes land in the same parser, so a session is counted identically
whichever way it arrived. Everything is recomputed from scratch on every run —
the whole drop folder is re-read, and spans are deduped on their exact
``(start, end)`` pair — so re-running is idempotent and a Shortcut whose window
overlaps the previous run's cannot double-count a session. That is what makes a
rolling window safe to send daily, which in turn is what makes a missed day
self-healing: send a fortnight every time and a fortnight of failed triggers
repairs itself.

The recompute is per day, though, and a window has an edge. Whatever the
Shortcut scopes by — a count of recent workouts, or a date range — its oldest
day is cut off partway through, so re-sending is only safe as long as a partial
recount cannot overwrite a complete one. ``_richer`` is what guarantees that: a
windowed payload may raise a day and never lower it. Widening the window makes
that guard matter more, not less, since a wider window slides back across more
days that are already recorded.

The payload may also be a list of **workout objects** rather than lines. That is
the practical case: Bend writes only `HKWorkout` records, stock Shortcuts cannot
read those at all, and the tools that can (Toolbox Pro's "Get Workouts", Health
Auto Export) hand back objects. Reading them here — unwrapping a `sessions`,
`workouts` or `data` wrapper, accepting whichever spelling of `startDate` the
producer uses, and filtering on source — keeps the phone side to "fetch the
workouts, post them", with no date formatting or source matching in Shortcuts.
Both are fiddly there and both fail silently.

Three line formats are also accepted, so anything that can produce text can use
whichever is easiest:

    2026-08-26T07:12:00-0400,2026-08-26T07:20:00-0400        # one session
    2026-08-26T07:12:00-0400,2026-08-26T07:20:00-0400,Wake Up # ... named
    2026-08-26,2                                             # a finished day
    2026-08-26,0                                             # ... a rest day

Spans are preferred. They go through the same union-then-count path as
``import_health.py``, so a session imported from a Shortcut and the same
session imported from a Health export produce the same number rather than two
subtly different ones.

Usage:
    python scripts/import_shortcut_stretching.py
    python scripts/import_shortcut_stretching.py --drop-dir ~/some/other/folder
    python scripts/import_shortcut_stretching.py --payload-file payload.json
    ... | python scripts/import_shortcut_stretching.py --payload-file -

Timezone matters here. A session is filed under the local date it started, so
whatever runs this must agree with the phone about what "local" means — see the
``TZ`` setting in ``.github/workflows/stretching.yml``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import sys

import habits_common as hc
import import_health as ih
from import_shortcut_sleep import parse_stamp

DROP_DIR = os.path.expanduser(
    "~/Library/Mobile Documents/com~apple~CloudDocs/habits/stretching"
)

# A stretch is minutes, not hours. Anything longer is a workout that was
# mis-tagged or a span whose end stamp failed to parse into the same day;
# either way it is not a Bend routine, and letting it through would blow out
# the minutes shown in the tooltip.
MAX_SESSION_H = 3

# Bend tops out around a dozen short routines in a day even for an enthusiast.
# A larger count means the shortcut sent a running total rather than a daily
# one, which would climb forever; refuse it rather than record it.
MAX_SESSIONS_PER_DAY = 20

# A bare ISO date anywhere in a line we could not read as a span or a count.
# Toolbox Pro's workout list renders as "Flexibility 2026-08-31 at 8:35 AM",
# and Shortcuts coerces a list variable to those display strings when it is
# dropped into a text field. One such line is one session on that date: less
# detail than a span, but the session count -- which is what the heatmap
# buckets on -- comes out exactly right.
ISO_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def parse_line(line: str) -> tuple[str, object] | None:
    """Classify one line as a session span or a finished day, or reject it."""
    line = line.strip().lstrip("﻿")
    if not line or line.startswith("#"):
        return None
    parts = [p.strip() for p in line.replace("\t", ",").split(",")]
    if len(parts) < 2:
        # No delimiter at all — a display string like
        # "Flexibility 2026-08-31 at 8:35 AM" rather than a pair.
        return _tally(line)

    # A finished day: a bare date and a session count.
    try:
        count = float(parts[1])
    except ValueError:
        count = None
    if count is not None:
        try:
            dt.date.fromisoformat(parts[0])
        except ValueError:
            return None
        if count == 0:
            # An explicit "nothing today". The simplest useful Shortcut sends
            # one line a day, and on a rest day that line reads `2026-08-29,0`.
            # Recognised and dropped rather than rejected: the heatmap already
            # reads an absent day as zero, and treating it as unparseable would
            # turn every rest day into a failed run — exactly the false alarm
            # --empty-ok exists to avoid.
            return ("skip", None)
        if count.is_integer() and 0 < count <= MAX_SESSIONS_PER_DAY:
            return ("day", (parts[0], int(count)))
        return None

    start, end = parse_stamp(parts[0]), parse_stamp(parts[1])
    if start is None or end is None or end <= start:
        return _tally(line)
    if (end - start).total_seconds() > MAX_SESSION_H * 3600:
        return _tally(line)
    label = parts[2] if len(parts) > 2 and parts[2] else ""
    return ("span", ((start.timestamp(), end.timestamp()), label))


def _tally(line: str) -> tuple[str, object] | None:
    """Last resort: one session on whatever ISO date the line mentions.

    Deliberately narrow. It needs a full ``YYYY-MM-DD``, so a line in another
    date format still fails loudly rather than being quietly half-read, and it
    only ever adds one session -- it cannot invent a number.
    """
    found = ISO_DATE.search(line)
    if not found:
        return None
    try:
        dt.date.fromisoformat(found.group(1))
    except ValueError:
        return None
    return ("tally", found.group(1))


# Key spellings different producers use for the same three fields. Nothing that
# can read an HKWorkout emits our line format: Toolbox Pro's "Get Workouts" and
# Health Auto Export both hand back objects, and they do not agree with each
# other on names. Reading the object directly is what keeps the phone side down
# to "fetch the workouts, post them" instead of a Repeat loop formatting dates
# by hand -- which is the part that cannot be tested from here.
_START_KEYS = ("start", "startdate", "start_date", "starttime", "start_time")
_END_KEYS = ("end", "enddate", "end_date", "endtime", "end_time")
_LABEL_KEYS = ("name", "workouttype", "workout_type", "activitytype",
               "activity_type", "activity", "type")
_SOURCE_KEYS = ("source", "sourcename", "source_name", "app", "appname",
                "app_name", "device")


def _pick(obj: dict, keys: tuple[str, ...]) -> str:
    """First non-empty value among ``keys``, matched ignoring case, _ and spaces."""
    flat = {
        str(k).casefold().replace("_", "").replace(" ", ""): v
        for k, v in obj.items()
    }
    for key in keys:
        val = flat.get(key.replace("_", ""))
        if val not in (None, "", []):
            return str(val)
    return ""


def _line_from_object(obj: dict, source: str) -> str | None:
    """Render one workout object as a ``start,end[,label]`` line, or None.

    ``source`` filters here rather than on the phone. Getting a Shortcut to
    filter workouts by their source app is the fiddliest part of the phone
    side and the part that fails silently when the string is slightly wrong;
    doing it in Python means it can be tested, and a mismatch shows up as a
    line count in the log rather than as an empty heatmap column. An object
    that carries no recognisable source field is kept, since there is nothing
    to judge it on.
    """
    start, end = _pick(obj, _START_KEYS), _pick(obj, _END_KEYS)
    if not start or not end:
        return None
    if source:
        got = _pick(obj, _SOURCE_KEYS)
        if got and source.casefold() not in got.casefold():
            return None
    label = _pick(obj, _LABEL_KEYS).replace(",", " ").strip()
    return f"{start},{end},{label}" if label else f"{start},{end}"


def _lines_from_json(decoded: object, source: str, _depth: int = 0) -> list[str] | None:
    """Pull session lines out of a decoded JSON payload, or None if it isn't one.

    A ``repository_dispatch`` arrives as ``{"sessions": "...\\n..."}``, and a
    Shortcut's "Get Contents of URL" body builder is happiest producing exactly
    that. Decoding it properly matters: the fallback in ``split_lines`` strips
    quotes and brackets as noise, which would leave a JSON payload's ``\\n``
    escapes as literal backslash-n and collapse every session onto one
    unparseable line.

    ``sessions`` may also arrive as a list of workout objects, or as a string
    that is itself JSON -- Shortcuts stringifies a list variable dropped into a
    text field, so a payload can end up encoded twice through no fault of
    whoever built the Shortcut.
    """
    if isinstance(decoded, dict):
        for key in ("sessions", "workouts", "data"):
            if key in decoded:
                return _lines_from_json(decoded[key], source, _depth + 1)
        line = _line_from_object(decoded, source)   # a bare object, not a wrapper
        return [line] if line else []

    if isinstance(decoded, str):
        stripped = decoded.strip()
        if _depth < 4 and stripped[:1] in "[{":
            try:
                return _lines_from_json(json.loads(stripped), source, _depth + 1)
            except ValueError:
                pass
        return decoded.splitlines()

    if isinstance(decoded, list):
        lines: list[str] = []
        for item in decoded:
            if isinstance(item, dict):
                line = _line_from_object(item, source)
                if line:
                    lines.append(line)
            else:
                lines.append(str(item))
        return lines
    return None


def split_lines(body: str, source: str = "") -> list[str]:
    """Break a drop file or a dispatch payload into candidate lines.

    Semicolons split as well as newlines. Shortcuts can build a multi-line text
    variable, but joining with a separator is markedly less fiddly, and a
    routine name never contains one.
    """
    stripped = body.strip()
    if stripped[:1] in "[{":
        try:
            decoded = json.loads(stripped)
        except ValueError:
            decoded = None
        lines = _lines_from_json(decoded, source) if decoded is not None else None
        if lines is not None:
            return [part for line in lines for part in line.split(";")]

    # Not JSON, or JSON in a shape we don't recognise: tolerate a shortcut that
    # emits something JSON-ish by treating the delimiters as noise.
    for ch in "[]{}\"'":
        body = body.replace(ch, "")
    return [part for line in body.splitlines() for part in line.split(";")]


def collect(
    body: str,
    spans: dict[tuple[float, float], str],
    days: dict[str, int],
    tally: dict[str, int],
    source: str = "",
) -> int:
    """Fold one file or payload into ``spans``/``days``; returns lines skipped."""
    skipped = 0
    for line in split_lines(body, source):
        got = parse_line(line)
        if got is None:
            skipped += 1 if line.strip() else 0
        elif got[0] == "span":
            span, label = got[1]
            # Keyed on the exact span, so the same session arriving in two
            # overlapping shortcut runs collapses to one entry.
            if label or span not in spans:
                spans[span] = label or spans.get(span, "")
        elif got[0] == "day":
            key, count = got[1]
            days[key] = max(days.get(key, 0), count)
        elif got[0] == "tally":
            # Summed, not maxed: two display-string lines on one date are two
            # sessions. An explicit count still wins over a tally below.
            key = str(got[1])
            tally[key] = min(tally.get(key, 0) + 1, MAX_SESSIONS_PER_DAY)
        # ("skip", None) is a line we understood and deliberately dropped — an
        # explicit zero-session day. Not counted as unparsed, so a rest day
        # still reads as an empty window rather than a broken payload.
    return skipped


def _combine(days: dict[str, int], tally: dict[str, int]) -> dict[str, int]:
    """Explicit per-day counts win over counts derived from date-only lines."""
    return {k: days.get(k) or tally.get(k, 0) for k in {*days, *tally}}


def read_payload(path: str, source: str = ""):
    """Return deduped spans, per-day counts, and unparsed line count.

    The unparsed count is what lets ``--empty-ok`` tell a rest week (a payload
    with nothing in it) apart from a Shortcut sending the wrong date format (a
    payload full of lines none of which parsed).
    """
    spans: dict[tuple[float, float], str] = {}
    days: dict[str, int] = {}
    tally: dict[str, int] = {}
    if path == "-":
        body = sys.stdin.read()
    else:
        with open(os.path.expanduser(path), encoding="utf-8-sig", errors="replace") as fh:
            body = fh.read()

    skipped = collect(body, spans, days, tally, source)
    hc.log(
        f"  payload: {len(spans)} session(s), {len(days)} pre-counted day(s)"
        + (f", {sum(tally.values())} counted from date-only line(s)" if tally else "")
        + (f", {skipped} line(s) unparsed" if skipped else "")
    )
    return spans, _combine(days, tally), skipped


def read_drop(drop_dir: str, source: str = ""):
    """Return deduped spans, per-day counts, and unparsed line count."""
    spans: dict[tuple[float, float], str] = {}
    days: dict[str, int] = {}
    tally: dict[str, int] = {}
    # README files are excluded deliberately: the folder documents its own
    # format, and worked examples in prose are one careless edit away from
    # being imported as real sessions.
    files = sorted(
        p for pattern in ("*.txt", "*.csv", "*.json")
        for p in glob.glob(os.path.join(drop_dir, pattern))
        if not os.path.basename(p).lower().startswith(("readme", "."))
    )
    if not files:
        return spans, days, 0

    skipped = 0
    for path in files:
        try:
            with open(path, encoding="utf-8-sig", errors="replace") as fh:
                body = fh.read()
        except OSError as exc:
            hc.log(f"  cannot read {os.path.basename(path)} ({exc})")
            continue
        skipped += collect(body, spans, days, tally, source)

    hc.log(
        f"  {len(files)} file(s): {len(spans)} session(s), "
        f"{len(days)} pre-counted day(s)"
        + (f", {sum(tally.values())} counted from date-only line(s)" if tally else "")
        + (f", {skipped} line(s) unparsed" if skipped else "")
    )
    return spans, _combine(days, tally), skipped


def _richer(old: dict, new: dict) -> dict:
    """Pick whichever of two records for the same day saw more of that day.

    A payload is authoritative about the sessions it *contains*, never about
    the ones it leaves out, and a rolling window always leaves some out. The
    shortcut scopes by a count of recent workouts rather than by a date, so
    its oldest day is cut off partway through; and the whole point of sending
    a window is that it keeps sliding back across days already recorded. Left
    to the per-day replace in ``write_habit``, that clipped edge overwrites a
    complete count with a partial one -- 2026-08-25 went from two sessions to
    one exactly that way on 2026-09-20, weeks after both had been recorded and
    with nothing wrong on the phone.

    Hand-transcribed days fail the same way for a different reason. Bend
    writes no HealthKit record at all for some routines (see
    ``bend-history.csv``), so a window re-covering such a day arrives carrying
    less than the file already holds and flattens the routine name out of the
    tooltip -- which is what happened to four days on 2026-09-11, the first
    run after they were backfilled.

    So a higher count wins, and on a tie the record carrying detail wins. That
    still lets a bare counted day upgrade into a real span with minutes and a
    routine name, while stopping a bare counted day from stripping either back
    out. The rule is deliberately one-way: a windowed payload can raise a day
    and never lower it. Correcting a day downwards -- a session deleted in
    Health, a duplicate that should never have counted -- is what a full
    export through ``import_health.py`` is for, and that path is untouched.
    """
    # .get rather than [] on the stored side: that record came off disk and may
    # have been hand-edited, and a missing key there should let the payload
    # through rather than wedge every future import behind a KeyError.
    was, now = old.get("value", 0), new["value"]
    if now != was:
        return new if now > was else old
    return new if new.get("extra") else old


def merge_and_write(
    spans: dict[tuple[float, float], str],
    counted: dict[str, int],
    days_back: int,
    out_dir: str,
) -> dict[str, dict]:
    """Count the sessions into days and write them, merging into the habit file."""
    since = hc.days_ago(days_back)
    # union() before counting, matching import_health.py: it collapses the
    # duplicate records two devices write for one session without merging
    # genuinely separate routines, which never overlap.
    merged = ih.union(list(spans))
    days = ih.stretch_days(merged, since)

    # Routine names ride along for the tooltip. They are attached after the
    # counting rather than during it so the session totals stay byte-identical
    # to what a Health export of the same sessions would produce.
    labels: dict[str, list[str]] = {}
    for (start, _end), label in sorted(spans.items()):
        if not label:
            continue
        key = hc.day_key(dt.datetime.fromtimestamp(start))
        if key in days and label not in labels.setdefault(key, []):
            labels[key].append(label)
    for key, names in labels.items():
        days[key].setdefault("extra", {})["routines"] = ", ".join(names)

    # Pre-counted days only fill dates the spans did not already cover, so a
    # shortcut that sends both forms cannot count a day twice.
    floor = hc.day_key(dt.datetime.combine(since, dt.time.min))
    for key, count in sorted(counted.items()):
        if key >= floor and key not in days:
            days[key] = hc.day(count)

    if not days:
        return days

    # Reconcile against the file before handing it to write_habit, whose merge
    # is a per-day replace and so would let the window's clipped edge undo a
    # day that was recorded completely weeks ago. See _richer.
    existing = hc.load_habit("stretching", out_dir).get("days") or {}
    held: list[str] = []
    for key, rec in sorted(days.items()):
        was = existing.get(key)
        if was is None:
            continue
        if _richer(was, rec) is was:
            days[key] = was
            if was != rec:
                held.append(key)
    if held:
        # Worth saying out loud: this is the window sliding off the back of a
        # day, not a session going missing, and the two look identical in the
        # heatmap afterwards.
        hc.log(
            f"  kept the recorded value on {len(held)} day(s) this window "
            f"covered only in part: {', '.join(held)}"
        )

    hc.write_habit(
        "stretching", "Stretching", "Bend", "sessions",
        days, merge=True, data_dir=out_dir,
    )
    return days


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--drop-dir", default=DROP_DIR, help="iCloud Drive folder to read")
    ap.add_argument("--payload-file", help="read session lines from this file "
                                           "('-' for stdin) instead of the drop folder")
    ap.add_argument("--days", type=int, default=120, help="how far back to keep")
    ap.add_argument("--source", default="Bend",
                    help="keep only workout objects whose source contains this "
                         "(default: Bend). Applies to object payloads only — a "
                         "plain line carries no source to judge. Pass '' to keep "
                         "everything.")
    ap.add_argument("--empty-ok", action="store_true",
                    help="succeed when the payload holds no sessions at all "
                         "(a rest week), while still failing on one that holds "
                         "lines none of which parsed")
    ap.add_argument("--out-dir", default=hc.DATA_DIR, help="habit JSON directory")
    args = ap.parse_args(argv)

    if args.payload_file:
        source = "stdin" if args.payload_file == "-" else args.payload_file
        hc.log(f"reading stretching payload from {source}")
        try:
            spans, counted, skipped = read_payload(args.payload_file, args.source)
        except OSError as exc:
            hc.log(f"cannot read payload ({exc})")
            return 1
    else:
        drop_dir = os.path.expanduser(args.drop_dir)
        if not os.path.isdir(drop_dir):
            hc.log(f"note: {drop_dir} not found — no shortcut drop to import")
            return 1
        hc.log(f"reading stretching drops from {drop_dir}")
        spans, counted, skipped = read_drop(drop_dir, args.source)

    if not spans and not counted:
        # An empty window and a misconfigured Shortcut both produce no sessions,
        # and only one of them is worth a red run every night. They are told
        # apart by whether anything was there to fail: no lines at all is a week
        # off, lines that all failed to parse is a bug.
        if args.empty_ok and not skipped:
            hc.log("no sessions in this window — nothing to import")
            return 0
        hc.log("nothing to import")
        return 1

    days = merge_and_write(spans, counted, args.days, args.out_dir)
    if not days:
        hc.log("no sessions in range — stretching.json left alone")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
