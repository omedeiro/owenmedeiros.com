# Getting Bend sessions onto /habits

Bend syncs its sessions into Apple Health. Apple Health is where the trail goes
cold: HealthKit is on-device only, there is no web API, and Health does not
reach the Mac either — it moves between devices through CloudKit's private
database, not as files. Nothing outside the phone can pull a Bend session out.

So the phone has to push. This is the phone-side half of that; the repo-side
half is `.github/workflows/stretching.yml` and
`scripts/import_shortcut_stretching.py`, both already in place.

## What the phone has to send

One line per session, in any of three shapes:

```
2026-08-26T07:12:00-0400,2026-08-26T07:20:00-0400            # a session
2026-08-26T07:12:00-0400,2026-08-26T07:20:00-0400,Wake Up    # ... named
2026-08-26,2                                                 # a finished day
2026-08-26,0                                                 # ... a rest day
```

The last form matters more than it looks: a Shortcut that sends one line a day
has to send *something* on a day you didn't stretch, and an explicit zero is
understood and dropped rather than treated as a broken payload.

Spans are preferred — they run through the same union-then-count path as a full
Health export, so a session that arrives this way and the same session pulled
out of `export.zip` produce the same number rather than two subtly different
ones. The third shape is there so a Shortcut that can only count sessions still
has something to send.

**Send a rolling window, not just today.** Whatever the sending tool scopes by —
a date range or a count of recent events — reach back well past yesterday. Spans
are deduped on their exact `(start, end)` pair and every affected day is
recounted from scratch, so re-sending a day cannot double-count it — which
means a run the phone misses (locked, offline, out of battery) is repaired by
the next one instead of leaving a permanent hole.

## Route A — straight to GitHub (the one that runs daily)

The Shortcut POSTs a `repository_dispatch`; the workflow merges, commits, and
Cloudflare redeploys. Nothing else has to be awake.

### 1. A token for the phone

GitHub → Settings → Developer settings → **Fine-grained personal access
tokens** → Generate new token:

- Repository access: **Only select repositories** → `omedeiro/owenmedeiros.com`
- Permissions → Repository permissions → **Contents: Read and write**
  (`repository_dispatch` is gated on Contents, not on Actions)
- Expiration: whatever you will actually remember to rotate

Nothing else. This token can write to one repo and do nothing else with the
account, which is the point of putting it on a phone.

### 2. What Shortcuts can and cannot read

**Stock Shortcuts cannot enumerate workouts.** `Find Health Samples` covers
quantity and category samples; an `HKWorkout` is neither, so *Workouts* simply
is not in its Type list. Toolbox Pro sells a `Get Workouts` action precisely
because the built-in actions can't do it. Two earlier drafts of this guide said
otherwise — first naming a "Find Workouts" action that does not exist, then
claiming `Find Health Samples` could be set to Workouts. Both were wrong. Don't
go looking again.

So before building anything, find out which readable type Bend writes.
**Health → your profile → Apps → Bend** lists exactly what it is permitted to
write, which settles it in one look. Failing that, add a bare
`Find Health Samples` action, set the Type below, filter
`Start Date is in the last 30 days`, and press ▶.

In order of preference:

1. **Mindful Minutes** — a category sample, so it *is* in the Type list. Several
   stretching apps write one per session alongside the workout. If Bend does,
   this is the whole answer: each sample carries a start and an end date, which
   is exactly what the span format below wants, and nothing else in this guide
   changes.
2. **Active Energy**, filtered to `Source is Bend` — a quantity sample, so
   always readable. Coarser, because one session writes many samples: enough to
   prove a session happened on a given day, not enough to cleanly separate two.
   Good enough for the `YYYY-MM-DD,1` day form, not for spans.

Whichever you use, note the exact **Source** string Bend reports. Guessing it is
the likeliest way to end up with a Shortcut that runs cleanly and sends nothing.

### 2b. Bend writes only workouts, so you need Toolbox Pro

Confirmed against this account: Health → profile → Apps → Bend shows Bend
*writing* Workouts and only reading Active Energy. No Mindful Minutes, and Bend
never appears in any Source list because it never writes a queryable sample
type. The stock app genuinely cannot see these sessions.

[Toolbox Pro](https://apps.apple.com/us/app/toolbox-pro-for-shortcuts/id1476205977)
closes that gap — free download, one-time unlock, and it adds a **Get Workouts**
action to the Shortcuts action list.

### 3. The Shortcut — two actions

The importer reads workout *objects* directly and filters them by source in
Python, so the phone does not have to format dates or match source strings.
Both of those are fiddly in Shortcuts and both fail silently. So:

1. **Get Workouts** (Toolbox Pro) — type **Flexibility**, **last 25 events**.
   Toolbox Pro scopes by a count of events, not by a date range, which suits
   this better than a window would: at roughly a session a day it reaches back
   about 25 days, so a run the phone misses is repaired by the next one for
   weeks rather than for a week. Re-sending costs nothing — days are recomputed
   from scratch, sessions dedupe, and the workflow skips the commit when nothing
   actually changed. No source filter needed; the importer does that.
2. **Get Contents of URL** — as in *Posting it* below, with the workouts from
   step 1 as `sessions`.

That is the entire phone side.

What arrives is a list of workout objects. The importer:

- reads `start`/`startDate`/`start_time` and the matching end key, whichever
  spelling the app uses, and unwraps a `sessions`, `workouts` or `data` wrapper
- keeps only workouts whose source contains **Bend**, so a Strava run in the
  same window is dropped rather than counted as stretching (`--source`, default
  `Bend`; pass `''` to keep everything)
- takes the workout's name or activity type as the `/habits` tooltip
- unwraps a payload that got JSON-encoded twice, which is what happens when
  Shortcuts stringifies a list variable dropped into a text field

If the whole window turns out to be Strava runs and no Bend, that is an empty
window — a green run and no commit, not a failure.

**Toolbox Pro filters by workout type, not source.** Set it to **Flexibility**,
which is what Bend files these under. That is also why a Strava run cannot leak
in through this route: a run is typed Running. Older Bend versions filed some
sessions as Yoga or Mind & Body, which a Flexibility-only filter would miss —
but before widening the filter to chase a missing day, check that the workout
is in Health at all. See *Some routines never reach Health* below; on this
account that, not the type filter, is what empties a day.

**If the workouts arrive as display strings**, e.g.
`Flexibility 2026-08-31 at 8:35 AM`, that is Shortcuts coercing a list variable
to text rather than to JSON. It still works: a line carrying a bare `YYYY-MM-DD`
and nothing else parseable counts as one session on that date, and two such
lines on one date count as two. You lose the minutes in the tooltip, nothing
else. If you later get real objects flowing, they overwrite the counted day and
the minutes appear — no cleanup needed.

The run's log prints the first 400 bytes of what arrived, so whichever shape it
is, the first run tells you.

### 3b. If you would rather not buy anything

The plain line formats above still work, so any other route that can produce
`start,end` lines feeds the same endpoint. The importer does not care what
produced them. A periodic `python scripts/import_health.py export.zip` also
remains available and needs no phone automation at all.

### Posting it

The final action in either version:

- **Get Contents of URL**
   - URL: `https://api.github.com/repos/omedeiro/owenmedeiros.com/dispatches`
   - Method: **POST**
   - Headers:
     | Key | Value |
     |---|---|
     | `Authorization` | `Bearer ghp_…` (the token from step 1) |
     | `Accept` | `application/vnd.github+json` |
     | `Content-Type` | `application/json` |
   - Request Body: **JSON**
     - `event_type` — Text — `stretching`
     - `client_payload` — Dictionary, containing:
       - `sessions` — Text — the line(s) you just built: the **Text** from the
         five-action version, or the **Combined Text** from the span version

**Run it once by hand.** The first run raises the Health permission prompt, and
a permission prompt inside a scheduled automation just fails. A successful run
returns an empty body and a 204; check the repo's Actions tab for an *Ingest
stretching* run.

### 4. Trigger it — not on a timer

**A time-of-day automation does not work for this, and the reason is structural.**
HealthKit refuses to read while the device is locked: access is relinquished ten
minutes after the screen locks and returns only when you unlock with Face ID or
a passcode. A fixed-time automation fires whether or not you happen to be
holding the phone, so on any night you are already asleep, `Get Workouts` cannot
reach the Health store and the Shortcut fails before it ever sends anything. It
looks like a network or token problem and is neither.

Trigger on something that *implies* an unlocked phone instead:

**Shortcuts → Automation → + → App → Bend → Is Closed → Run Immediately**,
with *Notify When Run* off.

The phone is unlocked by construction at that moment — you were just using it —
and the session gets pushed within seconds of finishing rather than hours later.

This is also why scoping by **last 25 events** rather than a date window
matters. The trigger does not have to fire every day, or reliably, or at any
particular time. Any one successful run recomputes roughly the last 25 days from
scratch, so a fortnight of failed triggers is repaired completely by the next
run that does go through. The pipeline is built to tolerate exactly this.

If you would rather keep a time-based automation as well, pick an hour you are
reliably awake and using the phone. It will fail silently on the nights you are
not, which is harmless — just noisy.

## Route B — iCloud Drive (fallback, needs the Mac)

The same lines written to a file in
`iCloud Drive/habits/stretching/` instead of POSTed. The nightly LaunchAgent
(`scripts/habits_daily.py`, 23:00) merges everything in that folder and commits.

Replace steps 4–5 above with a **Save File** action into that folder — one file
per run, any name; the whole folder is re-read every time, so files accumulate
harmlessly. `README*` is skipped on purpose, so a worked example written in
prose there can't be imported as real data.

This route only runs when the Mac is on, which is why it is the fallback. It
needs no token, which is why it is worth keeping.

## Checking it without a phone

Run the workflow by hand — Actions → **Ingest stretching** → *Run workflow* —
and paste lines into the input. Or from a shell:

```bash
curl -X POST https://api.github.com/repos/omedeiro/owenmedeiros.com/dispatches \
  -H "Authorization: Bearer $GH_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -d '{"event_type":"stretching","client_payload":{"sessions":"2026-08-26T07:12:00-0400,2026-08-26T07:20:00-0400,Wake Up"}}'
```

And locally, against a scratch directory so `src/data/habits` is left alone:

```bash
echo '2026-08-26T07:12:00-0400,2026-08-26T07:20:00-0400,Wake Up' \
  | python scripts/import_shortcut_stretching.py --payload-file - --out-dir /tmp/habits
```

## When nothing shows up

- **The run is green but no commit.** Either the window held nothing new — the
  job skips the commit when only `updated_at` would change, so re-sending the
  same seven days does not redeploy the site — or you did not stretch at all
  this week, which the job reports as "no sessions in this window" rather than
  as a failure.
- **The run is red at "Merge sessions".** The payload had lines in it and none
  of them parsed; the log prints how many. Usually the date format: it must be
  `yyyy-MM-dd'T'HH:mm:ssZ`, and `Z` there means the numeric offset (`-0400`),
  not a literal Z. This is deliberately the one case that fails loudly — an
  empty week is silent, a broken Shortcut is not.
- **Sessions land on the wrong day.** A session is filed under the local date it
  started, so the runner has to agree with the phone about "local". That is what
  `TZ: America/New_York` in the workflow is for — change it if you move.
- **The Shortcut finds no workouts.** Almost always the *Source* filter not
  matching what Bend actually calls itself. Strip every filter but
  `Start Date is in the last 30 days` and press ▶ — if workouts come back, the
  source string was wrong; if none do, the problem is upstream, in
  Bend → Settings → Apple Health, or Health → Sharing → Apps → Bend. If a full
  `export.zip` is handy, `python scripts/import_health.py export.zip
  --list-sources` prints every source and activity type it contains, which
  settles the question outright.
- **Some routines never reach Health.** Bend does not write every routine as a
  workout. On this account **Tech Neck** has never produced a single HealthKit
  record — confirmed 2026-09-10, by looking in Health rather than by inferring
  it from the Shortcut — while Hamstrings, Shoulders, Pre-Run and Posture Reset
  all arrive normally. Nothing on the phone side fixes this: the Shortcut can
  only forward what Bend wrote, so a wider type filter, a different source
  string and a longer window all return the same nothing. The tell is a routine
  that is missing on *every* day it appears in Bend's Recent History, rather
  than on scattered days. Those days have to come off the Recent History screen
  by hand into `scripts/bend-history.csv` — see *Sessions from before the sync*,
  which is the same path for the same reason.
- **Nothing has run at all.** The nightly *Refresh habit data* job warns when
  `stretching.json` has not moved in more than four days, so a Shortcut that
  quietly stopped shows up as an annotation rather than as a column that just
  stops growing.

## Sessions from before the sync

Bend's Health connection only writes sessions from the day it was enabled
onward; it never backfills. Anything earlier has to come off Bend's own Recent
History screen into `scripts/bend-history.csv`, merged by
`python scripts/backfill_stretching.py`. Those days are tagged
`"backfilled": true`.
