# The habits pipeline

A review of how `/habits` gets its data, written 2026-08-23 after rebuilding the
screen-time half. Covers what each pipeline does, which parts are trustworthy,
which are fragile, and what is worth doing next.

`AGENTS.md` is the operational runbook — how to run things, and the on-disk
details of the Apple data sources. This is the architectural view.

## What feeds the page

| Habit | Source | Transport | Schedule | Retention at source | State |
|---|---|---|---|---|---|
| Running | Strava | OAuth web API | CI, nightly | full history | 851 days, from 2019-01-01 |
| Push-ups | Puuush → Strava | OAuth web API + per-activity detail call | CI, nightly | full history | 1 day, from 2026-09-09 |
| Commits | GitHub | GraphQL contributions API | CI, nightly | full history | 418 days, from 2020-06-04 |
| Screen time | `knowledgeC.db` + Biome | local files on the Mac | LaunchAgent, 3×/day | **~28 days** | 29 days |
| Stretching | Bend → Apple Health | Shortcut → `repository_dispatch` | CI, on each push from the phone | ~unlimited | 19 days + whatever the phone has sent |
| Sleep | Apple Health | export, or Shortcut drop | manual / LaunchAgent | ~unlimited | **none — column removed** |

Four transports, in descending order of reliability: a web API anyone can call,
a push from a device that holds data nothing else can reach, a local file only
this Mac can read, and a human moving data by hand.

## The shared contract

One JSON file per habit in `src/data/habits/`, all the same shape:

```json
{ "id": "running", "label": "Running", "source": "Strava", "unit": "mi",
  "updated_at": "...", "days": { "2026-08-22": { "value": 5.2, "extra": {...} } } }
```

`value` is what the heatmap buckets on; `extra` is free-form detail for the
tooltip. Three properties of `habits_common` matter more than they look:

- **Writes merge by default.** Load-bearing, not a convenience. Screen time's
  sources retain about four weeks, so an overwriting write would silently
  discard every older day. The JSON file *is* the archive; nothing else holds
  that history.
- **Falsy extras are dropped**, so a day with no Mac usage has no `mac_h` key.
  Not missing data.
- **Standard library only.** No `pip install` anywhere, so the nightly job
  cannot break on a dependency release and the LaunchAgent can run under
  `/usr/bin/python3` rather than a conda environment.

## Pipeline by pipeline

### Running and commits — solid

Both call a documented web API with a token, chunk their queries, and merge.
`fetch_github.py` splits into 364-day windows because `contributionsCollection`
caps at a year; `fetch_strava.py` paginates. Both run in CI, and the workflow
warns and skips rather than failing when a credential is missing.

Nothing here is clever, which is the point. These are the two habits that can
be re-fetched from scratch at any time.

### Push-ups — solid, but shaped by the rate limit

Puuush posts each set to Strava as a generic `Workout` activity and puts the
count in the description as prose: `Total Reps: 15`. Two consequences follow,
and between them they account for the whole design of `build_pushup_days`.

The first is that the type cannot identify the activity — an Apple Watch
strength circuit is also a `Workout` — so the match is on the activity **name**
instead. The second is that `/athlete/activities` returns no `description` key
at all, so the count is reachable only through the per-activity detail endpoint,
one call per session. There is no structured alternative: Strava's
strength-workout breakdown returns an empty set list for these.

A naive implementation costs one call per session per run, which grows without
bound against a fixed 200-per-15-minutes limit. So the file is treated as a
cache: a day already recorded with the same number of sessions is reused
untouched, and only a new day, or one whose session count moved, is re-read.
Cost then tracks what changed rather than how long the history is — the first
run over a 730-day window spent exactly one detail call. Days resolve newest
first and stop at a budget, so a backlog sheds its oldest end rather than
today's, and re-reading on a changed count is what lets a session edited or
deleted in the app still correct itself.

The single fragile assumption is the wording. If a Puuush release renames
`Total Reps`, the parse stops matching — so it warns and skips the day rather
than writing a zero, which the page would otherwise render as an ordinary rest
day. A silent zero would be indistinguishable from not having trained.

### Screen time — sound, but only as durable as this Mac

Two sources, unioned per day:

- **Mac** — `knowledgeC.db`, `ZOBJECT` rows with `ZSTREAMNAME = '/app/usage'`.
  A documented schema.
- **iPhone** — `SEGB` segments under
  `~/Library/Biome/streams/restricted/App.InFocus/remote/<uuid>/`, parsed as
  protobuf records. Reverse-engineered; see `AGENTS.md` for the layout.

This is the fragile one, and it is worth being explicit about why it is
nonetheless trustworthy today:

- The segment header carries a record count, so a complete parse is checkable
  against the file itself.
- Intervals come only from explicit enter/leave pairs. An unclosed session is
  dropped rather than guessed at, which keeps a wrong parse loud instead of
  plausible.
- Parsing the Mac's *own* Biome stream gave 1163 sessions where `knowledgeC.db`
  independently reported 1080 over the same window — two unrelated formats
  agreeing.
- `implausible()` gates every write on future dates, days over 24 hours, and an
  absurd median.

An earlier version scanned the bytes for anything that decoded as a plausible
timestamp and reported an 18 h/day median with dates in 2033. The rewrite is
not just more careful; it fails differently. That distinction is the whole
design.

### Stretching — pushed from the phone

Counted in sessions per day rather than minutes, so days backfilled from Bend's
history screen sit on the same scale as days measured through HealthKit, with
nothing estimated.

Bend syncs into Apple Health, and Health goes no further on its own. The phone
therefore pushes: a scheduled Shortcut reads the last seven days of Bend
workouts, POSTs them as a `repository_dispatch`, and
`.github/workflows/stretching.yml` merges and commits them. Nothing but the
phone has to be awake, which is what separates this from the Mac-bound habits.
`docs/bend-stretching-shortcut.md` is the build guide.

Two properties make the daily schedule safe rather than merely convenient:

- **A rolling window, recomputed.** Spans are deduped on their exact
  `(start, end)` pair and every affected day is recounted from scratch, so
  re-sending a day cannot double-count it. A run the phone misses is repaired
  by the next one instead of leaving a permanent hole — the opposite of screen
  time, where a missed day is gone.
- **One parser, three transports.** The dispatch payload, the iCloud Drive drop
  file, and a full `export.zip` all reach the same `union()` and
  `stretch_days()`. A session counts the same however it arrived, so the routes
  can overlap without disagreeing.

The one thing the CI route needs that the local routes do not is a timezone.
Sessions are filed under the local date they started, so `stretching.yml` pins
`TZ: America/New_York`; on a UTC runner a 22:30 session would land on the next
day.

The earlier note here — that Bend was not syncing to Health at all, so
`bend-history.csv` was the only record — described the 2026-08-23 export and is
no longer true. `import_health.py --list-sources` settles it for any given
export.

### Sleep — no data, column removed

The importers work; the data does not exist. `InBed` records stop 2024-09-20,
REM/Deep staging stops 2023-12-13, and the only records since May 2026 start
mid-afternoon — naps. Importing them produced a 1.5 h/night median, so
`implausible_sleep()` now refuses a median under three hours.

Both routes remain wired: a full Health export (`import_health.py`) and a
scheduled iOS Shortcut dropping spans into iCloud Drive
(`import_shortcut_sleep.py`). Restoring the column is one `HABITS` entry in
`habits.astro` once sleep tracking is enabled on the phone.

## Principles that earned their place

Each of these exists because its absence produced wrong numbers:

- **Union, don't sum.** Overlapping app sessions are one wall-clock minute.
- **Guard, don't filter.** `implausible()` and `implausible_sleep()` refuse to
  write and say why. Trimming outliers until numbers look reasonable would hide
  the parse bug that produced them.
- **Explicit pairs only.** No interval without both ends recorded.
- **Exclude ambient.** StandBy is a third of raw iPhone time; `InBed` and
  `Awake` inflate sleep. Both are the device being present, not used.
- **Verify against a second source** wherever one exists.

## Known risks

1. **A lapse loses data permanently.** Screen time retains ~28 days at source.
   If the LaunchAgent stops — Mac off, Full Disk Access revoked by an OS
   update, repo moved — those days cannot be recovered afterward from
   anywhere. Two things now stand between a stall and a hole in the record.
   The agent gets three chances a day instead of one (login, 12:00, 23:00), so
   a single closed lid no longer costs a day; and the nightly job *fails* —
   rather than annotating a run nobody opens — once `screentime.json` is more
   than 2 days behind or `stretching.json` more than 4. The windows differ
   because screen time has a day for every day either device was used, while
   stretching only has days with sessions and rest days are real. Neither
   makes the loss recoverable; both buy the ~28 days of warning in which it
   still is. Stretching itself is no longer exposed to this at all: Health
   keeps its history indefinitely, so a gap there is filled by the next
   Shortcut run or by a full export.
2. **No tests.** The `SEGB` parser is hand-reverse-engineered against an
   undocumented format Apple changes between releases. It will break silently
   one day, and `implausible()` only catches failures that produce absurd
   numbers, not ones that produce merely wrong numbers.
3. **The LaunchAgent is the one link with no redundancy.** Its success path is
   verified now — it collected and pushed on five consecutive nights from
   2026-08-26 — but it has failed twice, in two different ways, and both are
   configuration that a reinstall can reintroduce. Full Disk Access is granted
   to `/usr/bin/python3` and only to that path, so the plist has to name it;
   pointing it at the Command Line Tools binary that `/usr/bin/python3` hands
   off to failed on 2026-09-03 with "authorization denied", because that path
   was never granted. And launchd's `PATH` omits `/opt/homebrew/bin`, so the
   LFS `pre-push` hook could not find `git-lfs` and every push aborted after a
   successful commit until the plist set `EnvironmentVariables` → `PATH`. Both
   live in the `scripts/` template so a reinstall cannot quietly lose them. What remains is that one machine,
   awake at one of three moments, is the only reader Screen Time data has: it
   stopped delivering after 2026-08-30 with nothing failing anywhere, which is
   what risk 1's check is for.
4. **Full Disk Access on the interpreter is a broad grant.** Narrower than
   `/bin/sh`, but any script run by that Python inherits it. That failure is no
   longer silent — the nightly check goes red within 2 days (risk 1) — but it is
   still invisible on the Mac itself, where the only symptom is an
   "authorization denied" line in `~/Library/Logs/habits-daily.log`.
5. **Single machine, single copy.** The habit JSON in git is the only archive
   of screen-time history.
6. **All-or-nothing sanity gating.** One implausible day blocks the entire
   write, including the good days alongside it.

## Worth doing next

Roughly in order of value per effort.

1. **Regression tests for the `SEGB` parser.** A synthetic segment with known
   contents, asserting session lengths and that StandBy and unclosed sessions
   are dropped. This was written and run by hand during the rewrite but never
   committed; it is the single highest-value gap given risk 2.
2. **Report which days failed the sanity check**, rather than only that some
   did. Keeps the refuse-don't-trim principle while making a single bad day
   diagnosable.
3. **Enable sleep tracking**, then restore the column. The pipeline is already
   built and tested on synthetic input — and now that stretching has a working
   phone-side push, sleep can reuse the same `repository_dispatch` route rather
   than waiting on the Mac.
4. **Surface the app breakdown.** The parser already reads bundle IDs, app
   versions, and build numbers, and throws all of it away. "3h 12m, mostly
   Safari" is a better tooltip than "3h 12m", at no parsing cost.
5. **Narrow the Full Disk Access grant** to a dedicated helper rather than the
   system Python.
6. **Reconsider the CI/local split.** Strava now has a connector available
   outside this repo; if habit collection ever moves off this Mac, the local
   Apple sources are the only genuinely machine-bound ones.
