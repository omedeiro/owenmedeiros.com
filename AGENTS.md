# Agent Instructions — owenmedeiros.com

Personal site built with Astro, deployed to Cloudflare Workers (static assets) at https://owenmedeiros.com.

## Commands

```bash
npm install
npm run dev       # local dev server
npm run build     # outputs to dist/
npm run preview   # preview production build
```

Deploys run automatically via Cloudflare Workers Builds on push to `main` (build command: `npm run build`; wrangler serves `dist/` as static assets).

## Structure

- `src/layouts/Base.astro` — site shell: nav, footer, all global CSS (single-column, minimal design)
- `src/layouts/Md.astro` — wrapper for markdown pages (renders `title` frontmatter as `<h1>`)
- `src/pages/` — all pages; markdown files use `layout: ../layouts/Md.astro` frontmatter
- `public/` — static assets (images, PDFs, `.m` files) served at root paths
- `wrangler.jsonc` — Cloudflare Worker config; custom domain `owenmedeiros.com`
- `astro.config.mjs` — redirects (`/contact`→`/about`, `/publications`→`/research`, `/thesis`→`/research`), math rendering (remark-math + rehype-katex)

## Adding pages

1. Create `src/pages/section/page-name.md` with frontmatter:
   ```yaml
   ---
   layout: ../../layouts/Md.astro   # depth-relative path
   title: Page Title
   ---
   ```
2. Images go in `public/section/` and are referenced with absolute paths (`/section/file.png`).
3. Add a link from the relevant index page (`src/pages/projects/index.md` etc.) — there is no auto-generated nav for content pages.

## Design rules

- Match darioamodei.com aesthetic: single ~42rem column, serif body, small sans-serif nav, no cards/grids/sidebars, no client-side JS.
- All styling lives in `Base.astro`; do not add per-page CSS files.
- **Five pages carry JS**, deliberately and narrowly. `/habits` passes `wide` to `Base` for a 52rem column (five heatmaps do not fit in 42rem) and carries an `is:inline` script for the heatmap tooltip. The four `/maths` pages each load one file from `public/maths/`: `aperiodic-tiles.js` for the tiling builder, `euler-spiral.js` for the curve viewer, `bertrand-paradox.js` for the chord sampler, and `mandelbrot.js` for the escape-time viewer. None can be done without a canvas, and all four stay at 42rem. The `wide` column remains `/habits` alone. Every other page stays 42rem and JS-free — do not generalise any of these exceptions without asking.
- All five keep their CSS in `Base.astro`, scoped by a class prefix (`.habits-*`, `.tiling*`, `.euler*`, `.bertrand*`, `.mandel-*`), rather than adding a per-page stylesheet. Each canvas viewer reads its palette back out of those custom properties with `getComputedStyle`, so light and dark are defined once, in the stylesheet.
- The tiling, spiral and Mandelbrot viewers pan and zoom, so their canvases take `touch-action: none` and own every gesture. The Bertrand sampler does not — it fits itself to the canvas — so it registers no pointer handlers and the page scrolls normally over it on a phone. Do not add pan and zoom to a view that has nowhere to pan to.
- LaTeX math works in markdown via `$...$` / `$$...$$` (KaTeX CSS loaded from CDN). It does **not** work in `.astro` pages: remark-math only runs on markdown, and Astro reads `{` in an `.astro` template as a JSX expression, so `\begin{pmatrix}` is a compile error. A page that needs both math and a script should be `.md` with the script tag inline — raw HTML and `<script src>` pass through untouched.
- **Display-math fences go on their own lines** — `$$`, newline, the expression, newline, `$$`. Opening with `$$x = 1` on one line parses as inline math instead, and the KaTeX error that follows swallows the whole rest of the document into one red `<span>`: prose stops being formatted and a trailing `<script src>` is escaped into text. `astro build` still exits 0, so grep the built HTML for `katex-error` rather than trusting the exit code.
- A display equation wider than the column scrolls in its own box (`.katex-display { overflow-x: auto }` in `Base.astro`) instead of pushing the whole page sideways on a phone.

## Content guidelines

**Never invent personal details:**
- No biographical filler ("passionate developer...")
- No assumed career history or education
- Stick to documented projects and technical facts
- If personal content is needed, ask the user

**Prefer concise technical content:** direct statements, specific tech details, real implementation notes.

## Habits

`/habits` renders five heatmaps from one JSON file per habit in `src/data/habits/`,
all sharing the same shape (`days: {"YYYY-MM-DD": {value, extra?}}`). The page buckets
each habit against **its own** quartiles, so unlike metrics share one five-step ramp.

Only two sources have web APIs. Apple has none for either Screen Time or Health —
`DeviceActivity` is sandboxed so usage data never leaves the device, and HealthKit is
on-device only — and neither does the Bend app, which syncs into Apple Health. Those
habits only move if the phone or the Mac pushes them.

| Habit | Script | Refresh |
|---|---|---|
| Running | `scripts/fetch_strava.py` | nightly, automatic |
| Push-ups | `scripts/fetch_strava.py` | nightly, automatic |
| Commits | `scripts/fetch_github.py` | nightly, automatic |
| Stretching | `scripts/import_shortcut_stretching.py --payload-file` | daily, automatic — the phone POSTs a `repository_dispatch` |
| Screen time | `scripts/fetch_screentime.py` | LaunchAgent, daily on the Mac |
| Sleep | `scripts/import_shortcut_sleep.py` | LaunchAgent, daily from an iCloud Drive drop |
| Stretching | `scripts/import_shortcut_stretching.py` | LaunchAgent fallback, from the same kind of drop |
| Stretching, Sleep | `scripts/import_health.py` | manual, after a Health export |

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

`docs/habits-pipeline.md` reviews these pipelines end to end — the shared JSON contract,
what each source can and cannot provide, known risks, and what is worth doing next. This
section stays the operational detail.

Stretching is counted in **sessions per day**, not minutes. Bend's own history screen
does not show session length, so counting sessions lets days backfilled from that screen
sit on the same scale as days measured through HealthKit, with nothing estimated.

`fetch_screentime.py` records **Mac usage from `knowledgeC.db` and iPhone usage from
Biome**. The iPhone half parses the `SEGB` segments under
`~/Library/Biome/streams/restricted/App.InFocus/remote/<uuid>/` as protobuf records —
a 32-byte file header, then `[4-byte CRC][4-byte state][protobuf][pad to 4]`. Records are
located by scanning for the state marker, not by walking lengths: a payload ending on a
4-byte boundary has no padding, so a length-walker runs into the next CRC and loses about
80% of the records. The header's record count at offset 4 is a free check on the parse.

Three things that are easy to get wrong here, all of which produced garbage before:

- **`tombstone/` directories hold sync bookkeeping, not usage.** The old byte-scanning
  version matched every path containing `InFocus`, so it was pairing deletion-record
  timestamps into sessions. That is where the 2033 dates and 26-hour days came from.
- **StandBy is not screen time.** The charging clock face is logged as an in-focus app and
  is a third of the raw total; it single-handedly turned ordinary days into 10-hour ones.
  See `AMBIENT`.
- **A synced Apple Watch looks exactly like a synced iPhone** — both are `remote/<uuid>/`
  and the UUID says nothing. `WATCH_MARKERS` separates them by bundle id.

`implausible()` still gates every write, and intervals come only from explicit
enter/leave pairs, so an unclosed session is dropped rather than guessed at.

Screen Time's own cross-device store is **not** on the Mac — there is no
`RMAdminStore-*.sqlite` and no ScreenTimeAgent container. Turning on "Share Across
Devices" registers the phone in `knowledgeC.db`'s `ZSYNCPEER`, but no `/app/*` row is ever
attributed to it; that view is assembled from CloudKit on demand. Don't go looking again.

## Apple Health, and why it needs a phone-side push

Health data does **not** reach the Mac. It syncs between devices through CloudKit's
private database — app-private and end-to-end encrypted — not as files in iCloud Drive.
Checked directly: 58 containers under `~/Library/Mobile Documents/`, none health-related,
and no `~/Library/Health` or Health container on disk. macOS has no Health app either.
Don't go looking for a local Health store; there isn't one.

**There is currently no sleep data to import, and the `/habits` sleep column is removed.**
The export tells the story: `InBed` records stop 2024-09-20, `AsleepREM`/`AsleepDeep`
staging stops 2023-12-13, and the only two `AsleepUnspecified` records since May 2026 both
start mid-afternoon — naps, not nights. A first import of them produced a 1.5 h/night
median, so `implausible_sleep()` now refuses anything under a 3 h median rather than
filing naps as sleep. Turning tracking on (Health → Sleep → Sleep Schedule, plus *Track
Sleep with Apple Watch*) starts collection; nothing backfills it. Restoring the column
means re-adding the import and one entry to `HABITS` in `habits.astro`.

Bend has **no public API** — no developer access, no export endpoint, nothing about
HealthKit on bend.com — so Apple Health is the only way a session leaves the phone. The
2026-08-23 export contained no Bend records at all; it does now, so the census in that
commit message is stale. `import_health.py --list-sources` prints what any given export
actually holds, and is the thing to run before believing either claim.

Health data therefore arrives one of three ways, all needing something on the phone:

1. **A scheduled iOS Shortcut POSTing to GitHub** — a `repository_dispatch` of type
   `stretching`, merged by `.github/workflows/stretching.yml` running
   `import_shortcut_stretching.py --payload-file`. This is the route that actually updates
   daily: nothing but the phone has to be awake. **`docs/bend-stretching-shortcut.md` is
   the build guide** — token scope, every action in the Shortcut, and what to check when
   nothing shows up.
2. **A scheduled iOS Shortcut writing to iCloud Drive** — into `habits/sleep/` or
   `habits/stretching/`, merged nightly by `import_shortcut_sleep.py` and
   `import_shortcut_stretching.py`. Those folders mirror to
   `~/Library/Mobile Documents/com~apple~CloudDocs/habits/` and, unlike Biome or
   `knowledgeC.db`, need **no Full Disk Access** to read. Each folder's `README.txt`
   documents its own accepted line formats. Kept as the token-free fallback; it only runs
   when the Mac does.
3. **A full Health export** (`import_health.py`), which also backfills stretching.

Routes 1 and 2 share every line of parsing and counting, so a session is counted
identically whichever way it arrived, and sending it both ways is harmless.

The stretching shortcut may need to read either workouts or mindful sessions, depending on
what Bend writes — it normalises to text lines on the phone, so neither the Mac nor the
runner cares which. Overlapping windows are safe: identical spans are deduped by exact
`(start, end)` and every affected day is recounted, so a 7-day window sent daily cannot
count a session twice — and a day the phone misses is repaired by the next run rather than
lost.

One thing the GitHub route needs that the Mac route does not: **a timezone**. Sessions are
filed under the local date they started, so the runner has to agree with the phone about
what "local" means. `TZ: America/New_York` in `stretching.yml` is what does that; without
it a 22:30 session lands on the following day.

Both file a night under the date you *woke up*, and the Shortcut route reuses
`import_health.sleep_days` and `union` so the two cannot disagree about the same night.
The drop folder is re-read in full every run and the result recomputed, so a shortcut
that writes the same night twice cannot double-count it.

Note that Full Disk Access is granted **per application**. Granting it to Terminal does not
give it to an agent running under another app — check what actually owns the shell before
concluding the grant failed.

`scripts/backfill_stretching.py` merges `scripts/bend-history.csv` — sessions transcribed
by hand from Bend's Recent History — into the same habit file. Bend's Health connection
only writes sessions from the day it was enabled onward and never backfills, so that CSV
is the only record of anything earlier. Backfilled days are tagged `"backfilled": true`.

The page maps a habit onto its five-step ramp by quartile, but switches to a direct
mapping when there are four or fewer distinct values. Stretching is almost always exactly
one session a day, and quartiles over a constant would paint every active day the palest
step — a column that looks empty when the habit is perfect.

All scripts are standard-library only (no pip install) and **merge** into the existing
JSON rather than overwriting it. That is load-bearing for screen time: macOS prunes
`knowledgeC.db` to roughly four weeks, so an overwriting write would destroy history.

`.github/workflows/habits.yml` runs the two API scripts nightly and commits
`src/data/habits/` straight to `main`, which triggers the usual Cloudflare deploy.
`.github/workflows/stretching.yml` does the same on a `repository_dispatch` from the
phone, whenever that arrives. Both are a deliberate, path-scoped exception to the
never-commit-to-`main` rule below — they apply to automated data commits only, never to
code. Both skip the commit when only `updated_at` changed, so a quiet day does not
trigger a pointless redeploy, and they share a `habits-refresh` concurrency group so the
two cannot race to push.

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

### One-time setup

1. **Strava** — create an app at <https://www.strava.com/settings/api>. Set
   **Authorization Callback Domain** to exactly `localhost` (no scheme, port, or path);
   Website can be anything. Then put `STRAVA_CLIENT_ID` and `STRAVA_CLIENT_SECRET` in
   `scripts/.env` and run `python scripts/fetch_strava.py --auth`, which opens the
   browser, catches the redirect on port 8721, and saves the refresh token.

   Do **not** copy the refresh token displayed on the API settings page. That one is
   permanently scoped to `read` and cannot list activities — it fails later with
   `401 activity:read_permission missing`. Only the `--auth` flow issues a token with
   `activity:read_all`, and the private-activity box on Strava's consent screen must
   stay ticked. `--auth --manual` falls back to pasting the redirect URL by hand.
2. **GitHub** — create a classic PAT with `read:user`. For private contributions also
   add `repo` and enable Settings → Profile → "Include private contributions".
3. **Repository secrets** — add `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`,
   `STRAVA_REFRESH_TOKEN`, and `GH_CONTRIB_TOKEN`. Optionally add `GH_ADMIN_TOKEN`
   (a PAT with `secrets:write`) so the workflow can store rotated Strava tokens itself;
   without it the job warns and you update `STRAVA_REFRESH_TOKEN` by hand.
4. **Screen time and sleep** — handled by the `com.owenmedeiros.habits` LaunchAgent,
   which runs `scripts/habits_daily.py` and commits to `main` only. Install it from the
   template in the repo, from the repo root — launchd does not expand `~` or `$HOME`,
   so the absolute paths are substituted in:

   ```bash
   mkdir -p ~/Library/LaunchAgents
   tmp=$(mktemp -t habits.plist)
   sed -e "s|{{HOME}}|$HOME|g" -e "s|{{REPO}}|$(pwd)|g" \
     scripts/com.owenmedeiros.habits.plist > "$tmp" \
     && plutil -lint "$tmp" \
     && mv "$tmp" ~/Library/LaunchAgents/com.owenmedeiros.habits.plist
   launchctl bootout gui/$(id -u)/com.owenmedeiros.habits 2>/dev/null
   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.owenmedeiros.habits.plist
   ```

   **Build it in a temp file and move it into place**; do not redirect straight onto the
   installed plist. The shell creates the target and truncates it *before* running the
   command on the left, so any failure — the template not on the branch you have checked
   out, a typo in the path — leaves a 0-byte plist behind, and a 0-byte plist unloads the
   service without saying anything. That is exactly how the agent went dark on
   2026-09-03. `plutil -lint` between the two steps means a malformed substitution is
   caught before it can replace a working file.

   It collects three times — at login, at 12:00, and at 23:00 — rather than once at
   23:00. `knowledgeC.db` and Biome are pruned to roughly four weeks, so a night the Mac
   was shut is history nothing can recover afterwards; the extra slots mean a missed
   23:00 is picked up at noon and a Mac that was off through both is caught at the next
   login. Re-running costs nothing, since `write_habit` merges and `habits_daily.py`
   skips the commit when no day changed.

   It needs **Full Disk Access on `/usr/bin/python3`**, the interpreter the plist names
   (System Settings → Privacy & Security → Full Disk Access → **+** → ⌘⇧G →
   `/usr/bin/python3`). The grant is per-binary and it has to be on that exact path:
   `/usr/bin/python3` is a stub sharing an inode with `/usr/bin/git` that hands off to
   the Command Line Tools interpreter, and it is tempting to conclude from that that the
   grant lands on the wrong binary — but this machine grants and honours it on the stub
   path. Pointing the plist at the resolved CLT binary instead failed immediately with
   "authorization denied", because nothing ever granted *that* path. Check rather than
   reason about it:

   ```bash
   sqlite3 "/Library/Application Support/com.apple.TCC/TCC.db" \
     "select client, auth_value from access
        where service = 'kTCCServiceSystemPolicyAllFiles'"
   ```

   `auth_value` 2 is allowed. A working Terminal run proves nothing here: interactive
   shells have their TCC decisions attributed to Terminal, so verify the agent itself
   with `launchctl kickstart -p gui/$(id -u)/com.owenmedeiros.habits` and read
   `~/Library/Logs/habits-daily.log`.

   The plist also sets `EnvironmentVariables` → `PATH` so that `/opt/homebrew/bin` is on
   it. launchd's default `PATH` is `/usr/bin:/bin:/usr/sbin:/sbin`, which has no
   `git-lfs`; see [Git LFS](#git-lfs) for what that breaks.
5. **Stretching, daily** — build the iOS Shortcut in
   `docs/bend-stretching-shortcut.md` and schedule it. That is the whole pipeline:
   Bend → Apple Health → Shortcut → `repository_dispatch` → `stretching.yml` → deploy.
   Check Bend → Settings → Apple Health is granted first, or the Shortcut finds nothing.
6. **Stretching and sleep, in bulk** — on iPhone: Health → profile → Export All Health
   Data, then `python scripts/import_health.py ~/Downloads/export.zip` and commit.
   One pass fills in both habits, and is the way to catch up a long gap.
7. **Stretching before the sync date** — add rows to `scripts/bend-history.csv` from
   Bend's Recent History screen and run `python scripts/backfill_stretching.py`.
   Only needed for sessions predating step 5; Bend's Health connection writes from the
   day it was enabled onward and never backfills.

## Publications

`src/pages/research.md` holds a static publications list. `references.bib` and `scripts/fetch_scholar.py` are kept for regenerating entries; update the markdown manually when new papers appear.

## Release / PR workflow (agent-driven changes)

All non-trivial changes (content edits, new pages, config changes) follow this process:

1. **Branch** — never commit directly to `main`. Create `feature/<short-slug>` from an up-to-date `main`.
2. **Version bump** — update `"version"` in `package.json` (semver). **Default to a patch bump** for most changes (content tweaks, link/copy edits, asset updates). Use minor for new pages/features, major only for site-wide redesigns or migrations.
3. **Changelog** — add a `## x.y.z — YYYY-MM-DD` entry at the top of `CHANGELOG.md` with `### Added` / `### Changed` / `### Removed` subsections as applicable.
4. **Verify** — run `npm run build` and confirm it succeeds.
5. **Commit** — one commit including the change, version bump, and changelog. Concise imperative subject line.
6. **PR** — push the branch and open a PR with `gh pr create` (summary of what/why).
7. **Merge** — use a **merge commit** (`gh pr merge --merge --delete-branch`), matching repo history. Then `git checkout main && git pull`.

Deploys to production happen automatically on merge to `main` via Cloudflare Workers Builds.

## Git LFS

PDFs tracked via LFS (`.gitattributes`). If pushing fails with "git-lfs not found":
```bash
git lfs install
git push
```

`.git/hooks/pre-push` tests for the binary with `command -v git-lfs` and exits non-zero
when it is missing, so a missing `git-lfs` fails the *push*, not the commit — the work is
committed locally and simply never leaves the machine. In an interactive shell Homebrew is
already on `PATH` and this does not come up; under **launchd it always does**, because
agents start with `PATH=/usr/bin:/bin:/usr/sbin:/sbin` and `git-lfs` lives in
`/opt/homebrew/bin`. That is why `scripts/com.owenmedeiros.habits.plist` sets
`EnvironmentVariables` → `PATH`. Any new LaunchAgent that pushes needs the same key;
without it the symptom is a log full of successful commits and `push failed`.
