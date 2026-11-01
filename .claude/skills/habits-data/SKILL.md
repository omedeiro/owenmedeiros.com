---
name: habits-data
description: How the /habits data pipeline works in this repo — the fetch scripts, the merge-on-write JSON contract, and the local Apple data sources (knowledgeC.db, Biome SEGB streams, Apple Health export). Load before touching anything in scripts/ that writes src/data/habits/, before debugging screen time, stretching, sleep, running, or commit numbers, and before investigating where iPhone or Mac usage data lives on disk. Records dead ends that have already been searched so they are not searched again.
---

# Habits data pipeline

Five habits feed `/habits`, one JSON file each in `src/data/habits/`. All fetch
scripts are **standard library only** — no pip install — so the nightly job
cannot break on a dependency release. `AGENTS.md` holds the short contract and the
script table; `docs/habits-setup.md` is the one-time setup; this skill covers what is
expensive to rediscover.

## Which scripts run where

| Habit | Script | Where |
|---|---|---|
| Running | `fetch_strava.py` | CI, nightly |
| Push-ups | `fetch_strava.py` | CI, nightly |
| Commits | `fetch_github.py` | CI, nightly |
| Screen time | `fetch_screentime.py` | **Mac only** — LaunchAgent, daily 23:00 |
| Sleep | `import_shortcut_sleep.py` | **Mac only** — LaunchAgent, from an iCloud Drive drop |
| Stretching | `import_shortcut_stretching.py --payload-file` | **CI**, on a `repository_dispatch` from the phone |
| Weight | `import_shortcut_weight.py --payload-file` | **CI**, on a `weight` `repository_dispatch` from the phone (Withings → Health → Shortcut) |
| Stretching | `import_shortcut_stretching.py` | **Mac only** — LaunchAgent fallback, from an iCloud Drive drop |
| Stretching, Sleep | `import_health.py` | **Mac only** — manual, after a Health export |

The Mac-only ones read Apple data no CI runner can reach. Do not try to move
them into `.github/workflows/habits.yml`. Stretching is the exception that
proves the rule: it is not *read* in CI, it is *pushed* to CI by an iOS
Shortcut, which is the only way data that lives in HealthKit can get anywhere.

## Push-ups: the count is prose, and costs a second call

Puuush posts sets to Strava as generic `Workout` activities, so `sport_type`
cannot identify them — an Apple Watch strength circuit is also a `Workout`.
Match on the activity **name**.

The rep count exists **only** as free text in the description
(`Total Reps: 15`). Two things already checked, so do not re-check them:
`/athlete/activities` returns no `description` key at all — the detail endpoint
is the only route — and `get_strength_workout_details` comes back with an empty
`exercise_sets` list for these, so there is no structured field waiting to be
found.

That means one extra call per session against a 200-per-15-minutes limit, which
is why `build_pushup_days` treats `pushups.json` as a cache: a day already
recorded with the same session count is reused and never re-read, so cost
tracks what changed rather than the length of the history. Do not "simplify"
that away — over the 730-day default window it is the difference between one
call and hundreds. A day that cannot be parsed is skipped with a warning, never
written as a zero; the page renders a zero as an ordinary rest day, which would
make a broken parse look like not having trained.

## The JSON contract

`habits_common.write_habit` **merges** by default. This is load-bearing:
`knowledgeC.db` and Biome are both pruned to roughly four weeks, so an
overwriting write would silently drop every older day. Never pass
`merge=False` to "clean up" a file.

`habits_common.day()` drops falsy extras to keep diffs small, so a day with no
Mac usage has no `mac_h` key at all. That is not missing data.

`/habits` derives its span from the earliest day any habit holds rather than a fixed
window, so backfilling an older range widens the chart automatically. Running reaches
back to 2019, screen time only ~4 weeks; each column simply starts where its source does.

When bumping the version, read `package.json` fully *before* opening it for writing —
`open(p,'w').write(open(p).read()...)` truncates the file first and silently empties it,
which broke the build in 2.1.2.

## Screen time: where the data actually is

**Mac** — `~/Library/Application Support/Knowledge/knowledgeC.db`, `ZOBJECT`
rows with `ZSTREAMNAME = '/app/usage'`. Documented schema, trustworthy.

**iPhone** — `~/Library/Biome/streams/restricted/App.InFocus/remote/<uuid>/`,
`SEGB` binary segments synced over iCloud. Near-live: records show up within
minutes of the phone being used.

### Dead ends — already searched, do not repeat

Screen Time's cross-device store is **not on the Mac**:

- No `RMAdminStore-*.sqlite` anywhere under `$HOME` (searched with Full Disk
  Access confirmed by a control query) and none in `/private/var/db`.
- No ScreenTimeAgent daemon container. `webContentRestrictions.sqlite` lives in
  the `com.apple.ciphermld` container and is unrelated.
- `com.apple.RemoteManagementAgent/Database/` is MDM configuration, not usage.
- `knowledgeC.db` is Mac-only in practice. Turning on "Share Across Devices"
  registers the phone in `ZSYNCPEER`, but **no `/app/*` row is ever attributed
  to it** — every one has a NULL `ZSOURCE`. The Screen Time UI assembles the
  cross-device view from CloudKit on demand.

The one untried route is a local iPhone backup, which contains the phone's own
Screen Time store with far deeper history than Biome's ~4 weeks. It needs a
backup to exist first (`~/Library/Application Support/MobileSync/Backup/`).

### SEGB format

32-byte file header, then records of
`[4-byte CRC][4-byte state][protobuf][zero pad to 4]`.

- Header offset 0 is `SEGB`; offset 4 is the **record count** — a free check
  that a parse is complete.
- Find records by scanning 4-aligned offsets for `state == 0x0A`. Do **not**
  walk by length: a payload ending on a 4-byte boundary has no padding, so a
  walker runs into the next record's CRC and desyncs, losing ~80% of records.
- Protobuf fields used: 3 = focus flag (1 enter, 0 leave), 4 = timestamp as a
  Mac-epoch double (add 978307200), 6 = bundle id. Also present: 1 transition
  reason, 9 app version, 10 build.

### Three traps that produced garbage before

1. **`tombstone/` directories are sync bookkeeping, not usage.** They contain
   segment ids and `biomesyncd`, no bundle ids. Reading them pairs deletion
   timestamps into fake sessions — the source of the "2033 dates and 26-hour
   days" failure. Filter on the path component, not on the filename.
2. **StandBy is not screen time.** (It single-handedly turned ordinary days into
   10-hour ones before it was excluded.) `com.apple.springboard.stand-by` — the
   charging clock face — is logged like an app and is roughly a third of the
   raw total. See `AMBIENT`. Apple excludes it.
3. **A synced Apple Watch looks exactly like a synced iPhone.** Both are
   `remote/<uuid>/`; the UUID says nothing. Separate them by bundle id share
   (`WATCH_MARKERS`), not by any single match.

Intervals must come from explicit enter/leave pairs. An unclosed session is
dropped, never guessed at — that is what keeps a wrong parse loud instead of
plausible. `implausible()` gates every write on future dates, >24h days, and an
absurd median; if it fires, the parse is wrong. Report it, do not trim outliers
until the numbers look reasonable.

### Sanity checks that actually validate a change

- Header record count == number of records parsed.
- Parsing this Mac's own `local/` Biome stream should roughly agree with
  `knowledgeC.db` session counts over the same window (1163 vs 1080 when this
  was last checked) — two unrelated formats, one answer.
- A synthetic `SEGB` segment with known contents round-trips.

## Apple Health: there is no local store

Health does **not** sync to the Mac. It moves between devices through CloudKit's private
database — app-private, end-to-end encrypted — not as files. Verified: 58 containers under
`~/Library/Mobile Documents/`, none health-related; no `~/Library/Health`, no Health
container, no Health app on macOS. HealthKit has no server-side API either, so there is
nothing for a connector to authenticate against. Do not search for this again.

**There is no sleep data on this account and the `/habits` sleep column is removed.**
`InBed` stops 2024-09-20, staging stops 2023-12-13, and the only records since May 2026
start mid-afternoon — naps. Importing them yielded a 1.5 h/night median, so
`implausible_sleep()` refuses a median under 3 h. Do not "fix" this by widening
`ASLEEP_VALUES` or dropping the guard; the data genuinely is not there until sleep
tracking is enabled on the phone. `sleep.json` and both importers remain, so restoring
the column is re-adding one `HABITS` entry in `habits.astro`.

Bend **does** sync into Apple Health. (An older note here said it did not; that described
the 2026-08-23 export, before the connection was on. `import_health.py --list-sources`
settles it for any given export — don't trust either claim from memory.) Health being
on-device only is what the plumbing works around, not a reason stretching is stuck.

Health only arrives if something on the phone pushes it:

- a scheduled iOS Shortcut POSTing a `repository_dispatch` of type `stretching`, merged in
  CI by `.github/workflows/stretching.yml`. **This is the daily route** — nothing but the
  phone has to be awake. `docs/bend-stretching-shortcut.md` builds it.
- a scheduled iOS Shortcut writing into `iCloud Drive/habits/sleep/` or
  `iCloud Drive/habits/stretching/`, merged by `import_shortcut_sleep.py` and
  `import_shortcut_stretching.py`. Token-free, but only runs when the Mac does.
- a full Health export, parsed by `import_health.py` (also backfills stretching)

All three land in the same `union()` and `stretch_days()`, so a session counts the same
however it arrived and the routes can overlap freely. Spans dedupe on the exact
`(start, end)` pair and every affected day is recounted, which is what makes a rolling
7-day window safe to send daily — and a missed day self-healing.

**Stock Shortcuts cannot enumerate workouts — do not go looking for a way.**
`Find Health Samples` covers quantity and category samples only; an `HKWorkout` is
neither, so *Workouts* is absent from its Type list, and there is no `Find Workouts`
action (two drafts of the guide claimed each of these in turn; both were wrong). Toolbox
Pro sells a `Get Workouts` action for exactly this gap. What *is* readable natively:
**Mindful Minutes** (a category sample — several stretching apps write one per session
alongside the workout, and it carries start and end dates, so it feeds the span format
unchanged) and **Active Energy** filtered by source (a quantity sample; many samples per
session, so it establishes that a day had a session but not how many). Check
Health → profile → Apps → Bend to see which Bend actually writes. **For this account it
is workouts only** — checked 2026-08-29 — so the stock app cannot reach it and Toolbox
Pro's `Get Workouts` is the route. `import_shortcut_stretching.py` therefore accepts a
list of workout **objects** and filters them by source itself (`--source`, default
`Bend`), which is what keeps the Shortcut down to two actions: date formatting and
source matching both fail silently in Shortcuts, so neither belongs there.

**Bend does not write every routine to Health, and no phone-side change fixes that.**
**Tech Neck** produces no HealthKit record at all — checked in Health on 2026-09-10,
after every Tech Neck day (9/2, 9/3, 9/9) came through the Shortcut empty while
Hamstrings, Shoulders, Pre-Run and Posture Reset on neighbouring days all arrived. Do
not diagnose this as the Toolbox Pro type filter dropping a Yoga/Mind & Body workout
and widen the filter; the workout does not exist to be filtered. The signature that
tells the two apart: a type-filter miss loses scattered days, a routine Bend never
writes is missing on *every* day it appears in Bend's Recent History. Such days can
only be transcribed by hand into `scripts/bend-history.csv` and merged with
`backfill_stretching.py` — the same path as pre-sync history.

**HealthKit cannot be read while the phone is locked** — access is relinquished ten
minutes after the screen locks and returns only on unlock. So a *time-of-day* Shortcuts
automation is the wrong trigger for anything reading Health: it fires whether or not the
phone is in use, and on a locked phone the read fails before any network call, which
presents as a vanished request rather than as a Health error. Trigger on **Bend → Is
Closed** instead; the phone is unlocked by construction. Scoping by last-25-events rather
than a date window is what makes an unreliable trigger acceptable — one successful run
recomputes ~25 days, so a fortnight of misses is repaired by the next success.

**The CI route needs `TZ` pinned.** A session is filed under the local date it started, so
`stretching.yml` sets `TZ: America/New_York`; on a bare UTC runner a 22:30 session lands
on the following day. This is tested and real, not theoretical.

Apple files `InBed` and `Awake` under the same sleep type as the asleep stages. Counting
them overstates a night — the same trap StandBy sets for screen time — so a tagged
category is filtered by `is_asleep()`. An untagged span cannot be told apart from a real
one, so the shortcut must send asleep samples only.

**iCloud Drive is readable without Full Disk Access** — it lives at
`~/Library/Mobile Documents/com~apple~CloudDocs/` and is not TCC-protected. That is what
makes the Shortcut route work where a Health store never could.

The Shortcut path reuses `import_health.sleep_days` and `union` on purpose: a night
imported from a drop file and the same night from a Health export must produce the same
number, not two subtly different ones. Both file a night under the **wake** date. The drop
folder is re-read in full each run and recomputed, so it is idempotent — and `README*` is
excluded from the scan, because worked examples in prose are one edit away from being
imported as real data. Each drop folder's `README.txt` documents its own accepted line
formats, so the formats are specified next to the data rather than only in the scripts.

## Full Disk Access

Granted **per application**, to the binary that opens the file. Consequences:

- An agent running under a different app than Terminal does **not** inherit
  Terminal's grant. Check what owns the shell before concluding a grant failed.
- TCC attributes access to the *responsible* parent app, so a `python3` spawned
  by another app is judged by that app, not by `/usr/bin/python3`.
- **Grant FDA to `/usr/bin/python3`, the path the plist names.** `/usr/bin/python3` is a
  stub — the same inode as `/usr/bin/git`, 78 hard links — that hands off to the Command
  Line Tools interpreter, and it is easy to conclude from that that a grant on it lands
  on the wrong binary. It does not, here: `TCC.db` allows `/usr/bin/python3` and holds no
  row for the CLT binary, and the agent read `knowledgeC.db` under it nightly through
  2026-09-02. Pointing the plist at
  `/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/bin/python3.9`
  instead failed on 2026-09-03 with a bare "authorization denied". Check the grant, do not
  reason about it:
  `sqlite3 "/Library/Application Support/com.apple.TCC/TCC.db" "select client, auth_value from access where service = 'kTCCServiceSystemPolicyAllFiles'"`
  — `auth_value` 2 is allowed. A shell wrapper is still ruled out: that would put the
  grant on `/bin/sh`.
- **launchd's `PATH` has no Homebrew in it.** Agents start with
  `/usr/bin:/bin:/usr/sbin:/sbin`, so `git-lfs` (`/opt/homebrew/bin/git-lfs`) is missing
  and this repo's LFS `pre-push` hook aborts every push while the commits pile up
  locally. The plist sets `EnvironmentVariables` → `PATH` to fix that.
- **A working Terminal run proves nothing about launchd.** Interactive shells have their
  TCC decisions attributed to the parent app, so anything run from Terminal inherits
  Terminal's grant. Verify the agent itself with `launchctl kickstart`.
- A denial raises `sqlite3.DatabaseError` ("authorization denied"), **not**
  `OperationalError`. Catch the parent class or the FDA hint never prints.

## Daily automation

Two schedules now. In CI, `.github/workflows/habits.yml` runs nightly (Strava, GitHub,
plus a staleness check that **fails the run** once `screentime.json` is more than 2 days
behind or `stretching.json` more than 4 — different windows because screen time has a day
for every day a device was used, while stretching only has days with sessions and rest
days are real) and `.github/workflows/stretching.yml` runs whenever the phone dispatches.
Both share the `habits-refresh` concurrency group so they cannot race to push.

On the Mac, `scripts/habits_daily.py`, run by
`~/Library/LaunchAgents/com.owenmedeiros.habits.plist` at login, 12:00 and 23:00, logging
to `~/Library/Logs/habits-daily.log`. The plist lives in the repo as
`scripts/com.owenmedeiros.habits.plist` with `{{HOME}}`/`{{REPO}}` placeholders (launchd
does not expand `~`); `docs/habits-setup.md` step 4 has the install. Three fire times rather than one
because the sources are pruned to ~4 weeks and a night the Mac was shut is gone — repeat
runs are free, since `write_habit` merges and the commit is skipped when no day changed.

It runs screen time and sleep independently — one failing does not stop the other —
collects on any branch (a skipped day is lost for good), and commits only on `main`, only the habit JSON files that changed, via a path-limited
commit, never mid-rebase or mid-merge.

Test it without waiting:
`launchctl kickstart -p gui/$(id -u)/com.owenmedeiros.habits`

## From AGENTS.md

Operational detail moved out of `AGENTS.md` when it was slimmed (2026-11-01). The
one-time setup list now lives in `docs/habits-setup.md`; the architectural review is
`docs/habits-pipeline.md`.

`/habits` renders five heatmaps from one JSON file per habit in `src/data/habits/`,
all sharing the same shape (`days: {"YYYY-MM-DD": {value, extra?}}`). The page buckets
each habit against **its own** quartiles, so unlike metrics share one five-step ramp.

The summary table scores each habit in the direction it is meant to move. Four of them
count a day as good the moment the thing happened; **screen time is the one to be cut
back**, so a day counts only when the Mac and the phone together stay at or under
`SCREEN_TIME_TARGET_H` (2h) — a habit entry supplies that rule as `counts`, and everything
else falls back to "recorded anything". Streaking a habit on "did it at all" when the goal
is less of it measures the sync, not the habit: before this, screen time's best streak was
simply the length of its history. A day with no record counts for neither direction.

Only two sources have web APIs. Apple has none for either Screen Time or Health —
`DeviceActivity` is sandboxed so usage data never leaves the device, and HealthKit is
on-device only — and neither does the Bend app, which syncs into Apple Health. Those
habits only move if the phone or the Mac pushes them.

Stretching is matched on the workout's **source name** (`Bend`), not its activity type,
because Bend has filed sessions as Flexibility, Yoga, and Mind & Body across versions.
`import_health.py --list-sources` prints what an export actually contains. The Shortcut
that pushes sessions off the phone should filter the same way, for the same reason —
`docs/bend-stretching-shortcut.md` builds it step by step.

Do not source stretching from Strava: its other "Workout" activities are strength
sessions. Push-ups now claim that same `sport_type`, which is why `fetch_strava.py`
picks them out by activity **name** rather than by type alone — an Apple Watch strength
circuit is otherwise indistinguishable from a push-up set.

Push-up reps are prose in the activity description (`Total Reps: 15`), written there by
the Puuush app. Strava has no structured field for them — its strength-workout breakdown
comes back empty for these — and `/athlete/activities` returns no `description` key at
all, so each session costs a second, per-activity call. `build_pushup_days` spends one
only on a day that is new or whose session count changed, reusing every other day
straight out of `pushups.json`; that is what keeps the 730-day default window well inside
Strava's 200-requests-per-15-minutes limit, and it is why the merge in `write_habit`
is depended on here rather than worked around. Re-reading a day whose count moved is what
lets a session edited or deleted after the fact still correct itself.

Bend has **no public API** — no developer access, no export endpoint, nothing about
HealthKit on bend.com — so Apple Health is the only way a session leaves the phone. The
2026-08-23 export contained no Bend records at all; it does now, so the census in that
commit message is stale. `import_health.py --list-sources` prints what any given export
actually holds, and is the thing to run before believing either claim.

The stretching shortcut may need to read either workouts or mindful sessions, depending on
what Bend writes — it normalises to text lines on the phone, so neither the Mac nor the
runner cares which. Overlapping windows are safe: identical spans are deduped by exact
`(start, end)` and every affected day is recounted, so a 7-day window sent daily cannot
count a session twice — and a day the phone misses is repaired by the next run rather than
lost.

`scripts/backfill_stretching.py` merges `scripts/bend-history.csv` — sessions transcribed
by hand from Bend's Recent History — into the same habit file. Bend's Health connection
only writes sessions from the day it was enabled onward and never backfills, so that CSV
is the only record of anything earlier. Backfilled days are tagged `"backfilled": true`.

The page maps a habit onto its five-step ramp by quartile, but switches to a direct
mapping when there are four or fewer distinct values. Stretching is almost always exactly
one session a day, and quartiles over a constant would paint every active day the palest
step — a column that looks empty when the habit is perfect.

`.github/workflows/habits.yml` runs the two API scripts nightly and commits
`src/data/habits/` straight to `main`, which triggers the usual Cloudflare deploy.
`.github/workflows/stretching.yml` does the same on a `repository_dispatch` from the
phone, whenever that arrives. Both are a deliberate, path-scoped exception to the
never-commit-to-`main` rule in `AGENTS.md` — they apply to automated data commits only,
never to code. Both skip the commit when only `updated_at` changed, so a quiet day does
not trigger a pointless redeploy, and they share a `habits-refresh` concurrency group so
the two cannot race to push. Since 2.18.0 the nightly job also runs
`python3 -m unittest discover -s tests` before its commit step, so a file that breaks
the JSON contract never lands on `main`.

The nightly job also **fails** when `stretching.json` or `screentime.json` stops
arriving. Neither has a schedule CI can check up on, so without it a deleted Shortcut or
a stopped LaunchAgent shows up only as a column that quietly stops growing — which is
exactly how stretching stalled for a week in August 2026. It annotated rather than failed
until 2.6.3, which was no better: screen time then sat two days stale and a human noticed
before the run did.

The windows are per habit, and deliberately different. Screen time is stale after **2
days**: a day is written whenever either device was used at all, so a healthy file is
never more than a day behind, and 2 catches a single missed LaunchAgent run while there
is still time to fix it — `knowledgeC.db` and Biome hold roughly four weeks, so the loss
is not permanent until then. Stretching is stale after **4 days**, because it only has
days on which a session happened; rest days are real (three 2-day gaps in August 2026)
and a 2-day window there would cry wolf every weekend.
