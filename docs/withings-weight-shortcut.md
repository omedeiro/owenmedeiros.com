# Getting Withings weigh-ins onto /habits

The scale uploads over Wi-Fi to Withings, the Withings app writes each reading
into Apple Health, and Health goes no further on its own. So, exactly as for
stretching, the phone pushes: a Shortcut reads the recent Weight samples and
POSTs them as a `repository_dispatch`, and `.github/workflows/weight.yml` runs
`scripts/import_shortcut_weight.py` to merge them into
`src/data/habits/weight.json`.

Weight is the easy case. It is a quantity sample, so stock `Find Health
Samples` can read it — no Toolbox Pro, unlike Bend's workouts.

(Withings also has a real OAuth web API, which could be fetched nightly in
`habits.yml` like Strava. Health is used instead because it needs no app
registration or refresh-token secret, and it reuses the token the phone already
holds for stretching.)

## Before you start

- **Withings app → Profile → Apple Health** is on, with **Weight** allowed to
  write. Check that a reading actually shows up in Health → Browse → Body
  Measurements → Weight before building anything.
- The phone already has the fine-grained GitHub token from
  `docs/bend-stretching-shortcut.md` (Contents: read and write on this repo).
  Reuse it.

## The Shortcut

1. **Find Health Samples**
   - Type: **Weight**
   - Filter: `Start Date` **is in the last** `30` **days**
   - Sort by: Start Date, Oldest First
2. **Repeat with Each** item in *Health Samples*:
   1. **Format Date** — *Repeat Item → Start Date*, Date Format **ISO 8601**,
      with *Include ISO 8601 Time* on. Gives `2026-10-28T07:12:00-04:00`.
   2. **Text** — `Formatted Date,Repeat Item → Value,Repeat Item → Unit`
      (three variables separated by commas, no spaces needed).
3. **Combine Text** — *Repeat Results*, with **New Lines**.
4. **Get Contents of URL**
   - URL: `https://api.github.com/repos/omedeiro/owenmedeiros.com/dispatches`
   - Method: **POST**
   - Headers: `Authorization: Bearer <token>`,
     `Accept: application/vnd.github+json`, `Content-Type: application/json`
   - Request Body: **JSON**
     - `event_type` — Text — `weight`
     - `client_payload` — Dictionary, containing `weights` — Text — *Combined Text*

Each line that arrives looks like `2026-10-28T07:12:00-04:00,181.4,lb`. Kilograms
are converted; a missing unit is taken as pounds.

**Run it once by hand** so the Health permission prompt appears outside an
automation. A 204 with an empty body is success; an *Ingest weight* run then
appears in the Actions tab.

## Trigger it

As with Bend, not on a timer: Health is unreadable while the phone is locked.
Use **Automation → App → Withings → Is Closed → Run Immediately**, notifications
off. Opening the Withings app is also what pulls a fresh weigh-in from the scale
into Health, so closing it is exactly the moment there is something new to send.

The 30-day window means any successful run repairs every run that failed before
it. Re-sending is harmless: each day is recomputed, and the workflow skips the
commit when nothing changed.

## What lands on the page

- One value per day: the **first** reading of that day, in lb, to one decimal.
  Its time goes into the tooltip, and so does the count when there were several.
  A later run whose window starts mid-morning cannot replace that first reading
  with an afternoon one, because the stored time wins when it is earlier.
- Shading is relative, so darker just means heavier than your usual range.
- *Good days* and *streaks* count days with a weigh-in — the habit is stepping
  on the scale. The amount column shows the latest reading and its change over
  the last 30 days.
- Readings outside 70–450 lb are refused rather than recorded: that is the
  shape a body-fat percentage or BMI in the value slot takes. A payload whose
  lines all fail to parse turns the run red; an empty window is green.

## Checking it without a phone

Actions → **Ingest weight** → *Run workflow*, and paste lines. Or locally,
against a scratch directory:

```bash
echo '2026-10-28T07:12:00-04:00,181.4,lb' \
  | TZ=America/New_York python scripts/import_shortcut_weight.py --payload-file - --out-dir /tmp/habits
```
