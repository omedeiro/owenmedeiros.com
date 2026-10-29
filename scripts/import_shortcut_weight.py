#!/usr/bin/env python3
"""Merge Withings weigh-ins pushed off the phone by an iOS Shortcut.

The Withings scale uploads over Wi-Fi to Withings' cloud, the Withings app
writes each reading into Apple Health, and from there it is the same problem as
stretching: HealthKit is on-device only, so a reading leaves the phone only if
something on the phone pushes it. A Shortcut POSTs a ``repository_dispatch`` of
type ``weight`` and ``.github/workflows/weight.yml`` runs this script with
``--payload-file``. ``docs/withings-weight-shortcut.md`` builds the phone side.

Weight is easier than stretching in one respect: it is a quantity sample, so
stock ``Find Health Samples`` can read it and no third-party action is needed.

One reading per line, in any of these shapes:

    2026-10-28T07:12:00-04:00,181.4,lb     # a weigh-in
    2026-10-28T07:12:00-0400,82.3,kg       # ... in kilograms
    2026-10-28 07:12:00 -0400,181.4 lb     # ... unit stuck to the value
    2026-10-28,181.4                       # a day, no time (assumed lb)

A JSON payload is also read: ``{"weights": "<lines>"}``, a list of objects with
a start/date key and a value/qty key, or Health Auto Export's
``{"data": {"metrics": [{"name": "weight_body_mass", "units": "lb", "data":
[...]}]}}``.

**Each day keeps its first reading.** Morning-before-breakfast is the number
worth comparing day to day, and an evening weigh-in after dinner is two or three
pounds of noise on top of it. The time of the kept reading rides along in
``extra.time`` so that a later run whose window cut off that morning -- a
"last 30 days" window measured from now starts mid-day -- cannot replace it with
the afternoon reading. Everything else is recomputed from the payload, so
re-sending a window is idempotent and a missed run is repaired by the next one.

Usage:
    python scripts/import_shortcut_weight.py --payload-file payload.txt
    ... | python scripts/import_shortcut_weight.py --payload-file -

Timezone matters, as for stretching: a reading is filed under the local date it
was taken, so ``weight.yml`` pins ``TZ: America/New_York``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys

import habits_common as hc
from import_shortcut_sleep import parse_stamp

KG_TO_LB = 2.20462

# Wide enough for any adult, narrow enough to refuse the readings a broken
# Shortcut produces: a body-fat percentage in the value slot, a BMI, a kg value
# labelled lb (or the reverse, which halves it). Refused, not clamped -- see
# "Guard, don't filter" in docs/habits-pipeline.md.
MIN_LB, MAX_LB = 70.0, 450.0

NUMBER = re.compile(r"(-?\d+(?:\.\d+)?)\s*([a-zA-Z]*)")

_STAMP_KEYS = ("startdate", "start", "date", "timestamp", "time", "enddate")
_VALUE_KEYS = ("value", "qty", "quantity", "weight", "bodymass")
_UNIT_KEYS = ("unit", "units")


def to_lb(value: float, unit: str) -> float | None:
    """Convert to pounds, or None for a unit that is not a mass."""
    unit = unit.strip().casefold().rstrip(".")
    if unit in ("", "lb", "lbs", "pound", "pounds"):
        return value
    if unit in ("kg", "kgs", "kilogram", "kilograms"):
        return value * KG_TO_LB
    if unit in ("st", "stone"):
        return value * 14
    return None


def parse_line(line: str) -> tuple[dt.datetime | dt.date, float] | None:
    """Read one ``when,value[,unit]`` line into (when, pounds), or None."""
    line = line.strip().lstrip("﻿")
    if not line or line.startswith("#"):
        return None
    parts = [p.strip() for p in line.replace("\t", ",").split(",")]
    if len(parts) < 2:
        # Typically a bare value with no date -- what arrives when the Text
        # action holds only the sample's Value. Undatable, so unparsed.
        return None

    when: dt.datetime | dt.date | None = parse_stamp(parts[0])
    if when is None:
        try:
            when = dt.date.fromisoformat(parts[0])
        except ValueError:
            return None

    found = NUMBER.fullmatch(parts[1])
    if not found:
        return None
    unit = found.group(2) or (parts[2] if len(parts) > 2 else "")
    pounds = to_lb(float(found.group(1)), unit)
    if pounds is None or not MIN_LB <= pounds <= MAX_LB:
        return None
    return when, pounds


def _pick(obj: dict, keys: tuple[str, ...]) -> str:
    flat = {str(k).casefold().replace("_", "").replace(" ", ""): v for k, v in obj.items()}
    for key in keys:
        val = flat.get(key)
        if val not in (None, "", []):
            return str(val)
    return ""


def _lines_from_json(decoded: object, unit: str = "", _depth: int = 0) -> list[str]:
    """Flatten any of the accepted JSON shapes into ``when,value,unit`` lines."""
    if _depth > 6:
        return []
    if isinstance(decoded, str):
        stripped = decoded.strip()
        if stripped[:1] in "[{":
            try:
                return _lines_from_json(json.loads(stripped), unit, _depth + 1)
            except ValueError:
                pass
        return [part for line in decoded.splitlines() for part in line.split(";")]

    if isinstance(decoded, list):
        return [ln for item in decoded for ln in _lines_from_json(item, unit, _depth + 1)]

    if not isinstance(decoded, dict):
        return []

    # Health Auto Export: metrics carry their unit once, at the metric level.
    if "metrics" in decoded:
        lines = []
        for metric in decoded.get("metrics") or []:
            if isinstance(metric, dict) and "weight" in str(metric.get("name", "")).casefold():
                lines += _lines_from_json(metric.get("data") or [], str(metric.get("units", "")), _depth + 1)
        return lines
    # "sessions" because the first Shortcut built for this was a copy of the
    # Bend one, and kept its body key.
    for key in ("weights", "weight", "samples", "sessions", "data"):
        if key in decoded and isinstance(decoded[key], (str, list, dict)):
            return _lines_from_json(decoded[key], unit, _depth + 1)

    when, value = _pick(decoded, _STAMP_KEYS), _pick(decoded, _VALUE_KEYS)
    if not when or not value:
        # Returned as a line rather than dropped, so it is counted as unparsed:
        # an object we cannot read must fail the run, not pass as an empty week.
        return [json.dumps(decoded)] if decoded else []
    return [f"{when},{value},{_pick(decoded, _UNIT_KEYS) or unit}"]


def split_lines(body: str) -> list[str]:
    stripped = body.strip()
    if stripped[:1] in "[{":
        try:
            return _lines_from_json(json.loads(stripped))
        except ValueError:
            pass
    return [part for line in body.splitlines() for part in line.split(";")]


def build_days(readings: list[tuple[dt.datetime | dt.date, float]]) -> dict[str, dict]:
    """First reading of each local day, with its time and the day's count."""
    by_day: dict[str, list[tuple[str, float]]] = {}
    for when, pounds in readings:
        if isinstance(when, dt.datetime):
            # Aware stamps are moved into the runner's zone (TZ in weight.yml)
            # before taking the date; a naive one is already local.
            local = when.astimezone() if when.tzinfo else when
            key, clock = hc.day_key(local), local.strftime("%H:%M")
        else:
            key, clock = hc.day_key(when), ""
        by_day.setdefault(key, []).append((clock, pounds))

    days: dict[str, dict] = {}
    for key, rows in by_day.items():
        # A dated-only row sorts first on "", which is fine: it has no time to
        # lose to, and a payload mixing both forms for one day is a curiosity.
        rows = sorted(set(rows))
        clock, pounds = rows[0]
        days[key] = hc.day(round(pounds, 1), time=clock, readings=len(rows) if len(rows) > 1 else 0)
    return days


def keep_earlier(days: dict[str, dict], existing: dict[str, dict]) -> dict[str, dict]:
    """Don't let a window that started mid-day replace an earlier reading."""
    out = {}
    for key, rec in days.items():
        old = existing.get(key)
        old_t = (old or {}).get("extra", {}).get("time", "")
        new_t = rec.get("extra", {}).get("time", "")
        out[key] = old if old and old_t and new_t and old_t < new_t else rec
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--payload-file", required=True, help="readings to merge ('-' for stdin)")
    ap.add_argument("--days", type=int, default=400, help="ignore readings older than this")
    ap.add_argument("--empty-ok", action="store_true",
                    help="succeed on a payload with no readings at all, while still "
                         "failing on one whose lines all failed to parse")
    ap.add_argument("--out-dir", default=hc.DATA_DIR, help="habit JSON directory")
    args = ap.parse_args(argv)

    try:
        if args.payload_file == "-":
            body = sys.stdin.read()
        else:
            with open(os.path.expanduser(args.payload_file), encoding="utf-8-sig", errors="replace") as fh:
                body = fh.read()
    except OSError as exc:
        hc.log(f"cannot read payload ({exc})")
        return 1

    lines = [ln for ln in split_lines(body) if ln.strip()]
    readings = [r for r in map(parse_line, lines) if r]
    skipped = len(lines) - len(readings)
    hc.log(f"  payload: {len(readings)} reading(s)" + (f", {skipped} line(s) unparsed" if skipped else ""))

    if not readings:
        if args.empty_ok and not lines:
            hc.log("no weigh-ins in this window — nothing to import")
            return 0
        hc.log("nothing to import")
        return 1

    floor = hc.day_key(hc.days_ago(args.days))
    days = {k: v for k, v in build_days(readings).items() if k >= floor}
    if not days:
        hc.log("no readings in range — weight.json left alone")
        return 1

    existing = hc.load_habit("weight", args.out_dir).get("days") or {}
    hc.write_habit(
        "weight", "Weight", "Withings", "lb",
        keep_earlier(days, existing), merge=True, data_dir=args.out_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
