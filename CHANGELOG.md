# Changelog

## 2.8.3 — 2026-09-12

### Added

- An **ORCID** link in the site footer and in the `/about` contact list, after Google Scholar

## 2.8.2 — 2026-09-12

### Added

- A **Google Scholar** link in the site footer and in the `/about` contact list, after LinkedIn. The profile id is the one `scripts/fetch_scholar.py` already defaults to, so the link and the publication-fetching script now point at the same profile rather than only the script knowing it

## 2.8.1 — 2026-09-12

### Changed

- Push-ups now sit in the rightmost column on `/habits` rather than second from the left. It is the newest habit and the shortest history, so leading with it put the emptiest block next to the longest one; moving it to the end lets the columns read roughly oldest-first. The summary table and the SVG `aria-label` follow the same order

## 2.8.0 — 2026-09-10

### Added

- A **push-ups** column on `/habits`, the fifth heatmap, counting reps a day. The Puuush app posts each set to Strava, so the data arrives on the nightly Strava refresh with no new credential and no new transport — but it arrives awkwardly. Puuush files sets as a generic `Workout`, which an Apple Watch strength circuit also is, so `fetch_strava.py` matches on the activity **name** rather than on `sport_type`; and the count exists only as free text in the description (`Total Reps: 15`), which `/athlete/activities` does not return at all. There is no structured field to read instead — Strava's strength-workout breakdown comes back with an empty set list for these — so every session costs a second, per-activity call
- `build_pushup_days` therefore treats `pushups.json` as a cache rather than an output: a day already recorded with the same number of sessions is reused untouched and never re-read, so cost tracks what changed instead of how long the history is. The first run across the 730-day default window spent exactly one detail call, which is what keeps this inside Strava's 200-per-15-minutes limit as the column fills in. Days resolve newest first and stop at a budget, so a backlog sheds its oldest end rather than today's, and re-reading a day whose session count moved is what lets a set edited or deleted in the app correct itself afterwards
- A day whose description cannot be parsed is skipped with a warning rather than written as a zero. The page renders a zero as an ordinary rest day, so a Puuush release that reworded `Total Reps` would otherwise present as not having trained — the one fragile assumption here, made loud instead of plausible

### Changed

- `/habits` says five things rather than four, and names Strava as the source of both running and push-ups; the summary table, the SVG `aria-label`, and the page description follow
- `AGENTS.md`, `docs/habits-pipeline.md`, and the `habits-data` skill record why push-ups are matched by name, why the description is the only source of the count, and why the cache is load-bearing rather than an optimisation

## 2.7.2 — 2026-09-10

### Added

- Five Bend sessions the automated route never delivered — 2026-08-24, 09-02, 09-03, 09-06 and 09-09 — transcribed from the app's Recent History into `scripts/bend-history.csv`. Only the missing days were added: `write_habit` merges per day, so re-transcribing a day HealthKit already recorded would overwrite a measured count with a hand-typed 1

### Changed

- `/habits` no longer describes stretching as recorded by hand. It has arrived through Apple Health and the phone's Shortcut since 2.3.0; hand transcription is now the exception, for the routines Bend does not write to Health at all
- The heatmap legend said shading was relative to each habit's quartiles. Habits with four or fewer distinct values — stretching, nearly always one session — are mapped straight onto the ramp steps instead, so the legend now says "range"

### Fixed

- `docs/bend-stretching-shortcut.md` blamed a missing day on Toolbox Pro's Flexibility-only workout-type filter dropping a session Bend had filed as Yoga or Mind & Body. That is the wrong diagnosis for this account: **Bend writes no HealthKit record at all for Tech Neck**, confirmed by looking in Health on 2026-09-10, which is why all three Tech Neck days were empty while neighbouring routines arrived. Widening the type filter cannot help — the workout does not exist to be filtered. The doc and the `habits-data` skill now record the signature that tells the two apart: a type-filter miss loses scattered days, a routine Bend never writes is missing on every day it appears in Recent History

## 2.7.1 — 2026-09-06

### Fixed

- `scripts/habits_daily.py` rebases onto `origin/main` before pushing. A push to a branch that has moved on is rejected outright, and the agent swallows the failure to stay alive, so the commit sat unpushed while every run still reported success — three days of screen time were stranded that way at the start of September, surfacing only when someone read the log. Nothing upstream prevents it: `habits.yml` and `stretching.yml` push habit data of their own, so `main` moves without this machine involved. The pull carries `--autostash`, because collection can leave unrelated files dirty and a rebase refuses to start on a dirty tree, and `--no-edit`, so nothing can open `$EDITOR` on an agent with no terminal attached. A conflict aborts the rebase rather than leaving it half-applied, which would make `busy()` refuse to commit on every later run and turn one bad day into a silent permanent stall

## 2.7.0 — 2026-09-05

### Added

- `/maths/mandelbrot` — an interactive Mandelbrot and Julia viewer, and the fifth page on the site to carry JS. Drag to pan, pinch or scroll to zoom, **Orbit** to follow the sequence `z0, z1, z2, ...` under the pointer and read off the period of the cycle it settles into. Switching to **Julia** takes `c` from wherever the parameter plane is centred and puts a thumbnail of the Mandelbrot set in the corner; dragging its marker moves `c` live, so the Fatou-Julia dichotomy — connected inside `M`, Cantor dust outside — becomes a gesture rather than a claim. The fragment records mode, centre and magnification, so a view is a link, and is applied on `hashchange` as well as at load
- `public/maths/mandelbrot.js` — the viewer. Escape time is smoothed to a fractional count, `nu = n - log2(ln|z_n| / ln R)` at `R = 256`, which is `-log2` of the escape potential up to an additive constant: checked against a reference at `R = 1e8` over 60,000 parameters, the two agree to `4e-6` (at `R = 4` the error is `0.07`, enough to see the bands move). The image is built by progressive refinement — 16x16 blocks, then 8, 4, 2, 1, each pass computing only what the last one skipped, which totals exactly one image, so the coarse preview costs nothing — and the work is time-sliced across frames, with the last finished image blitted under the new transform while a gesture is live
- Interior points are shortcut three ways: closed-form tests for the main cardioid and the period-2 disc, then Brent-style period checking for everything else. Over 200,000 random parameters at a budget of 6,000 iterations the shortcuts and plain iteration disagree nowhere, and pixel-counting the area with the same kernel gives 1.509 against the accepted 1.5065
- `.mandel-*` styles in `Base.astro`, including the five palette stops the script bakes into a 2,048-entry lookup table. The inset thumbnail ramps towards `--mandel-mark` rather than towards the ink, which is what keeps it legible in dark mode where the ink and the panel background are both nearly black

### Changed

- The `/maths` index lists four pages rather than three and gains a `description` of its own; it had been falling back to the site-wide one, which is about superconducting electronics. With Bertrand now sampling live, all four run in the browser
- The zoom stops at `x1e14`, measured rather than guessed: at `x1e13` a pixel near `c = -0.74` is `5e-16` against a `1.6e-16` gap between doubles and the image is clean, at `x1e14` it goes grainy, and at `x1e15` whole rows of pixels collapse onto one value and the view is bands of noise. The readout says when the view is into that range
- `AGENTS.md` and the habits CSS comment count five JS pages; the habits block still described itself as the only one

## 2.6.5 — 2026-09-05

### Added

- Every entry in the `/research` publications list is now a link, resolved to the publisher of record: DOIs (`doi.org`) for journal articles, `opg.optica.org` abstracts for the three CLEO papers, IEEE Xplore for the two conference papers without a findable DOI, arXiv for the two preprints, and the DSpace handles already used above for the two theses

### Changed

- The two theses duplicated in the publications list now point at the same MIT handles as the entries in the Theses section
- Both Nature Electronics entries now carry the journal's own citation, checked against Nature's "Cite this article" block. The 2026 memory-array paper moves from the advance-online `1–9` to its final `9, 69–77`, and the 2025 rectifier loses the `(5)` — Nature cites by volume and page only, and that issue number came from Google Scholar rather than the publisher

### Removed

- *Control of bulk superconductivity via surface-bound electric fields in ion-gated niobium nitride thin films* (Proc. 11th Conf. "Solid State Surfaces and Interfaces", 2020). The proceedings volume has no DOI or publisher record anywhere online, so the entry could not be linked like the rest. It remains in `references.bib`

## 2.6.4 — 2026-09-03

### Fixed

- The `com.owenmedeiros.habits` LaunchAgent template named the wrong Python. 2.6.3 pointed it at the resolved Command Line Tools binary on the theory that `/usr/bin/python3` is a shim whose Full Disk Access grant can never apply; that reasoning is wrong on this machine, and the change broke the agent the first time it was installed from the template — two consecutive runs on 2026-09-03 died with "cannot open knowledgeC.db (authorization denied)". TCC keys the decision to the path launchd is told to execute, and `/Library/Application Support/com.apple.TCC/TCC.db` allows `/usr/bin/python3` while holding no row of any kind for the CLT binary. Back to `/usr/bin/python3`, which is what AGENTS.md documented all along and what read `knowledgeC.db` nightly through 2026-09-02. The comment now records the evidence and the `sqlite3` query to re-check it, instead of an argument from how the binary is built
- The template had no `EnvironmentVariables` key, so every push the agent made aborted. launchd starts jobs with `PATH=/usr/bin:/bin:/usr/sbin:/sbin`, which does not contain `git-lfs` (`/opt/homebrew/bin/git-lfs`); this repo tracks PDFs through LFS and its `pre-push` hook tests for the binary with `command -v git-lfs`, so the run committed, logged `push failed ... 'git-lfs' was not found on your path`, and nothing reached GitHub. Setting `PATH` to put Homebrew first fixed it on the next run. Independent of the interpreter, and needed by any future agent that pushes
- The documented install redirected `sed` output straight onto `~/Library/LaunchAgents/com.owenmedeiros.habits.plist`. The shell truncates the target before the command on the left runs, so a failure — most easily the template not being on the branch you have checked out — leaves a 0-byte plist, which unloads the service silently. That is how the agent went dark on 2026-09-03. Now it builds into a temp file, runs `plutil -lint`, and moves the result into place, so a working install survives a failed reinstall

## 2.6.3 — 2026-09-03

### Changed

- The screen-time LaunchAgent now collects **three times a day** — at login, at 12:00 and at 23:00 — instead of only at 23:00. `knowledgeC.db` and Biome are pruned to roughly four weeks, so a night the Mac was shut is a day of history no later run can recover, and a single 23:00 slot meant one closed lid cost a day. The noon run picks up a missed night; `RunAtLoad` catches a Mac that was off through both. Repeat runs are free by construction: `write_habit` merges, so the noon run's partial day is overwritten by the fuller number at 23:00, and `habits_daily.py` skips the commit when no day changed
- The nightly staleness check **fails the run** rather than printing a warning annotation, and screen time's window drops from 4 days to 2. Annotating was no better than nothing: screen time stopped delivering after 2026-08-30 and sat stale for days with every run green, because a `::warning::` is only visible to someone who opens the run. Stretching keeps the 4-day window — it only has days on which a session happened, and rest days are real (three 2-day gaps in August 2026), so 2 days there would cry wolf every weekend. Both habits are checked before the step exits, so one stall cannot hide another

### Added

- `scripts/com.owenmedeiros.habits.plist`, the LaunchAgent as a checked-in template with `{{HOME}}`/`{{REPO}}` placeholders and a one-line `sed` install in AGENTS.md. It was previously only ever a file on one Mac, which is how it came to point at `/usr/bin/python3` — a shared Xcode shim that re-execs the real interpreter, so the Full Disk Access grant on it never applied and `knowledgeC.db` failed with a bare "authorization denied". The template names the resolved Command Line Tools binary and says why, so a reinstall cannot quietly reintroduce that

### Fixed

- `habits_daily.py`'s docstring named a plist and a log file that have not existed since the agent stopped being screen-time-only (`com.owenmedeiros.screentime.plist`, `screentime-daily.log`), and still recommended pointing launchd at `/usr/bin/python3`, which is the exact configuration that failed

## 2.6.2 — 2026-09-01

### Fixed

- The guide told you to schedule the Shortcut as a daily time-of-day automation at 11:30 PM. That cannot work: HealthKit refuses to read while the device is locked — access is relinquished ten minutes after the screen locks and returns only on unlock — so a fixed-time automation fires on a locked phone, `Get Workouts` cannot reach the Health store, and the Shortcut dies before it sends anything. The failure presents as a request that never arrives, which looks like a network or token fault and is neither. Documented the **Bend → Is Closed** app trigger instead, where the phone is unlocked by construction and the session is pushed seconds after it happens. Also spelled out why last-25-events scoping is what makes an unreliable trigger tolerable: any single successful run recomputes ~25 days, so a run of failures is repaired completely by the next success

## 2.6.1 — 2026-09-01

### Fixed

- The Shortcut guide told you to set Toolbox Pro's Get Workouts to a seven-day date range. It scopes by a count of recent events instead, so that setting does not exist. Documented as **last 25 events**, which suits the pipeline better than a window would: at roughly a session a day it reaches back about 25 days, so a missed run is repaired by the next one for weeks rather than for a week

## 2.6.0 — 2026-08-31

### Added
- Bend → `/habits` now updates on its own, without the Mac. A scheduled iOS Shortcut reads the last seven days of Bend workouts out of Apple Health and POSTs them as a `repository_dispatch`; `.github/workflows/stretching.yml` merges them into `stretching.json`, commits, and the usual Cloudflare deploy follows. HealthKit is on-device only and Health does not reach the Mac, so a push from the phone is the only transport that exists — the previous route had one, but it landed in iCloud Drive and was picked up by a LaunchAgent, so it only ran when the Mac happened to be on. That is why stretching stopped at 2026-08-22
- `docs/bend-stretching-shortcut.md` — the phone-side build guide that `AGENTS.md` has referred to since 2.2.0 without it existing: token scope, every action in the Shortcut, how to test the route with no phone involved, and what each failure mode looks like. Leads with a five-action Shortcut that sends only today's count, since it proves the whole pipe with no loop and no date arithmetic; the seven-day span version is a drop-in replacement, and a span overwrites the day-count for the same date, so upgrading needs no cleanup
- A date-only fallback, so a payload of workout *display strings* still counts correctly. Shortcuts coerces a list variable dropped into a text field to strings like `Flexibility 2026-08-31 at 8:35 AM` rather than to JSON, and that is a plausible shape for what Toolbox Pro's `Get Workouts` hands over. A line carrying a bare `YYYY-MM-DD` and nothing else parseable now counts as one session on that date, and two such lines on one date count as two — summed, where an explicit `date,count` is still taken at its word. Deliberately narrow: it needs a full ISO date, so a line in any other date format still fails loudly rather than being quietly half-read. Session counts, which is what the heatmap buckets on, come out exact; only the tooltip minutes are lost, and a later object payload overwrites the day and restores them
- The ingest workflow logs the first 400 bytes of the payload. The shape of what the phone sends is the one thing that cannot be checked from a laptop, and a run that parsed nothing was otherwise indistinguishable from a run that received nothing. No new exposure — the same timestamps are committed to `stretching.json`
- Workout **objects** as a payload, not just text lines. Bend writes only `HKWorkout` records, which stock Shortcuts cannot read at all, so the payload realistically comes from a tool that hands back objects (Toolbox Pro's `Get Workouts`, Health Auto Export). The importer unwraps a `sessions`/`workouts`/`data` wrapper, accepts whichever spelling of `startDate` the producer uses, survives a payload JSON-encoded twice (what Shortcuts does to a list variable dropped into a text field), and filters on source itself via `--source` (default `Bend`), so a Strava run in the same window is dropped rather than counted as stretching. This is what keeps the phone side to two actions — date formatting and source matching both fail silently in Shortcuts, so neither belongs there
- `--payload-file` on `import_shortcut_stretching.py`, reading the same session lines from a file or stdin instead of the drop folder. The drop folder, the dispatch payload, and a full `export.zip` all reach the same `union()` and `stretch_days()`, so a session counts identically however it arrived and the routes can overlap without disagreeing
- A staleness warning in the nightly job when `stretching.json` or `screentime.json` has not moved in more than four days. Neither has a schedule CI can check up on, so a deleted Shortcut or a stopped LaunchAgent previously showed up only as a column that quietly stopped growing

### Fixed

- Stock Shortcuts cannot enumerate workouts at all: `Find Health Samples` covers quantity and category samples, an `HKWorkout` is neither, and *Workouts* is simply absent from its Type list (Toolbox Pro sells a `Get Workouts` action for exactly this gap). The guide now says so plainly and redirects to what *is* readable — Mindful Minutes, a category sample carrying start and end dates that feeds the span format unchanged, or Active Energy filtered by source — with the three paid/manual fallbacks if Bend writes only workouts. Recorded in the `habits-data` skill as a dead end
- The guide named a "Find Workouts" Shortcuts action that does not exist. The real action is **Find Health Samples** with its *Type* set to Workouts, and per-item dates come from **Get Details of Health Sample** rather than off the repeat item directly. It now also opens by running that one action bare, which is the only reliable way to learn what Bend calls itself in the *Source* field — guessing that string is the likeliest way to end up with a Shortcut that runs cleanly and sends nothing
- An explicit zero-session day (`2026-08-29,0`) was rejected as an unparseable line, so the simplest possible Shortcut — one that sends today's count once a day — would have failed its run every rest day, which is exactly the false alarm `--empty-ok` exists to prevent. A zero count is now recognised and dropped; the heatmap already reads an absent day as zero
- Sessions were counted against the runner's local date, which on a UTC runner files a 22:30 session under the following day. `stretching.yml` pins `TZ: America/New_York`
- A JSON payload collapsed into one unparseable line. `split_lines` now decodes a JSON object or array properly before falling back to stripping delimiters as noise; it also splits on semicolons, since joining lines with a separator is markedly less fiddly in Shortcuts than building a multi-line text variable

### Changed

- `AGENTS.md`, `docs/habits-pipeline.md`, and the `habits-data` skill all recorded that Bend does not sync to Apple Health. That described the 2026-08-23 export, taken before the connection was on, and it is no longer true — all three now point at `import_health.py --list-sources` as the way to settle it for a given export rather than asserting either answer

## 2.5.0 — 2026-08-30

### Added

- `/maths/bertrand-paradox` is interactive. Four ways of drawing a chord at random — two points on the circle, a point along a random radius, a point anywhere in the disc, and the line through two interior points — each sampled live, with a **Compare all four** mode that puts them side by side. **Show → Midpoints** swaps each chord for its own midpoint, which is where the methods separate most clearly, and **Run** streams the sample in so the estimate can be watched settling
- `public/maths/bertrand-paradox.js` — the sampler. Every rotation-invariant method reduces to a density on `p`, the chord's distance from the centre, and the chord beats the triangle side exactly when `p < 1/2`; all four densities are known in closed form, so the strip under the circle draws the sampled histogram against the exact curve and shades the half whose area *is* the answer. Sampling runs off a seeded generator, one stream per method, so raising the count extends the sample rather than drawing an unrelated one
- A fourth method Bertrand did not list: the line through two uniform points in the disc. Pairs of interior points on a chord number as the cube of its length, so the induced density is `(16/3pi)(1-p^2)^(3/2)` and the answer is `1/3 + 3*sqrt(3)/(4*pi) ~ 0.7468`, checked against 4e6 Monte Carlo samples
- The page now says outright that the question has every answer in `(0,1)`, not three: `f(p) = (a+1)p^a` gives `P = (1/2)^(a+1)`, and two of Bertrand's own answers are already in that family. Plus Jaynes' invariance argument for `1/2`, and why it does not make the other constructions wrong

### Changed

- The `/maths` index no longer singles Bertrand out as the static one; all three pages run live

### Fixed

- The old listing's second method — *fix one endpoint, choose the other at random* — was labelled `P = 1/2`. It is the first method with the rotation already applied, and gives `1/3`. The page now makes that the point of its own section, since it is the most common way to get the paradox wrong

### Removed

- The MATLAB listing and `bertrand_paradox.m`. The four methods run live, at any sample count. `bertrand.png` stays as the page's opening figure, with a caption noting that its third panel's colours are inverted — the code coloured `|y| > r/2` as the long case when that is exactly the short one

## 2.4.2 — 2026-08-30

### Changed

- `/projects/tdgl-simulation` is rebuilt around the current solver. The page had one MATLAB gif and a code sample for an API (`TDGLSolver`) that no longer exists; it now carries eight figures from [`omedeiro/nanowire_tdgl`](https://github.com/omedeiro/nanowire_tdgl) and the results they demonstrate — the 3x3 array of 4 um holes where the flux front stalls at the array perimeter and field-cooling is the only way to trap anything, the S/I/S ring that expels flux to 9.2 mT because the plane screens rather than because the hole is small, vortex nucleation, screening currents around a hole, and the cross-sections against the London and pair-breaking-wall solutions. Every number on the page comes from the repo's own figures
- Source link points at `nanowire_tdgl` (the Python package) rather than `simulation6336`, which is now credited as the MATLAB original. The install and quick-start snippets are the real `tdgl3d` API
- Both MATLAB gifs are kept, moved into a closing provenance section

### Added

- `public/projects/tdgl/` gains six PNGs and two gifs. Every figure links to its full-resolution file, since the four- and six-panel ones are not legible at 42rem, and every image is `loading="lazy"` — the page is 8 MB of figures and only the first one is above the fold
- `nb-hole-array-trapped.gif` is requantised to a 64-colour palette with dithering off: 8.4 MB to 3.1 MB with no visible change to the physics panel, since dithering adds exactly the per-pixel noise GIF's run-length coding cannot compress

## 2.4.1 — 2026-08-30

### Changed

- The running habit is measured in miles rather than kilometres. `fetch_strava.py` divides Strava's metres by 1609.344 on the way out and writes `"unit": "mi"`, and the existing 853 days in `running.json` were converted in place — `extra.distance_m` still carries the raw metres, so the conversion is reversible

## 2.4.0 — 2026-08-30

### Added

- `/maths/euler-spiral` is interactive. One curve reached three ways, each with its own sliders: the Fresnel integrals, the turtle walk the page used to show in MATLAB, and the road transition the curve exists for. Drag to pan, pinch or scroll to zoom, **Trace** to walk a point along the curve with the circle matching its curvature at each moment. The strip under the plot draws curvature against arc length, which is the definition of the curve as a straight line
- `public/maths/euler-spiral.js` — the viewer. Curves are sampled by tangent turn rather than by parameter, since the Fresnel phase grows quadratically and the coils at `s = 8` need 25x the samples per unit length that the straight middle does; the midpoint rule then lands within `2e-5` of tabulated `C(t)` and `S(t)` across the whole slider range. Every sample carries its own closed-form curvature rather than having it differenced back out of the polyline

### Changed

- The transition comparison holds both alignments between the **same two straights**, the way the choice actually presents itself, rather than starting both from one straight. Sharing an entry tangent instead makes the two curves diverge by roughly the tangent distance — half a radius at 90° — which swamps the shift `p = L²/24R` the comparison exists to show. Between fixed tangents the difference is exactly that shift plus the earlier start, and both are checked against the geometry rather than taken from the series
- The `/maths` index now calls out Bertrand as the one page that is still a MATLAB listing; the tiling and Euler spiral pages both run live

### Fixed

- A display equation too wide for the 42rem column now scrolls in its own box rather than pushing the page sideways on a phone (`.katex-display { overflow-x: auto }`)

### Removed

- The MATLAB listing, `euler_spiral.m` and `euler.png`. The turtle mode is that loop, running live

## 2.3.0 — 2026-08-29

### Added
- `/maths/aperiodic-tiles` — a tiling builder you can pan and zoom on a phone or a desktop. Three tilings, built three different ways: Penrose P3 rhombs by substitution of the two Robinson triangles, Ammann–Beenker by cut and project from `Z^4` through an octagonal window, and the hat from a stored patch. Pointer events cover mouse, trackpad and touch through one code path, so a drag pans, two fingers pinch and a flick glides; the canvas centre is clamped to stay over the patch, since one determined scroll otherwise leaves a blank canvas with no clue which way to come back
- `public/maths/hat-search.mjs` — the derivation of the hat, as a runnable script. It enumerates all 10,209 8-kite polykites, keeps the 341 whose outline is a simple 13-gon, asks an exact-cover solver which of those can fill discs of radius 5, 12 and 30, and picks out the one that is forced to mix reflections in the ratio `1 : phi^4`. That one is the hat. Runs in about eight seconds, standard library only. The page's hat patch (475 tiles, radius 44) comes from the same solver, and is stored rather than generated because the search grows exponentially — that radius took three random restarts and `8.8e8` nodes, and four restarts at radius 50 each gave up after `2.5e9`

### Changed

- `/maths` index no longer claims every page is MATLAB, which stopped being true with the tiling page

## 2.2.0 — 2026-08-26

Released without a changelog entry; recorded here after the fact.

### Added

- `scripts/import_shortcut_stretching.py` — merges Bend sessions dropped into `iCloud Drive/habits/stretching/` by a scheduled iOS Shortcut, wired into the nightly LaunchAgent. Reuses `import_health`'s `union()` and `stretch_days()` so a session imported from a Shortcut and the same session from a full Health export produce the same number. Spans dedupe on the exact `(start, end)` pair, so a 7-day window run daily cannot double-count

### Changed

- `/habits` column order: running, commits, screen time, stretching

## 2.1.5 — 2026-08-25

### Fixed

- Missing space before several links on the home page ("work developed<a>", "and some<a>", "publications</a>,<a>"). Astro's HTML compressor drops whitespace-only runs that span a newline, so any link the source starts on its own line lost the space in front of it. `compressHTML` is now off — the pages are small and JS-free, so keeping the authored whitespace costs less than reflowing prose around the compressor

## 2.1.4 — 2026-08-24

### Changed

- `/habits` tooltips latch open on tap: tapping a cell keeps it up, tapping it again dismisses it, and tapping another cell moves it there. Previously a tap showed the tooltip only while the finger was down, because a touch pointer is destroyed on release and fires `pointerleave` immediately after `pointerdown`.
- The tapped cell is outlined while its tooltip is open, since touch has no hover state to show which cell is being read.
- Dismissing on page scroll is replaced by dismissing on horizontal scroll of the chart, which is the case that actually leaves the tooltip misaligned. Vertical scroll needs no handling — the tooltip travels with the chart.

## 2.1.3 — 2026-08-23

### Fixed

- Empty `package.json`, committed in 2.1.2 by a version-bump one-liner that opened the file for writing before reading it. `main` could not build until this landed

### Added

- Full history on `/habits`: running back to 2019-01-01 (228 → 851 days) and commits to 2020-06-04 (275 → 418), re-fetched with a wider window. The chart no longer spans a hardcoded 104 weeks — it derives its span from the earliest day any habit holds, so older data stops being clipped as it accumulates
- `implausible_sleep()` in `import_health.py` — refuses to write when the median night is under three hours, the shape an Apple Watch worn for afternoon naps but not overnight produces. A guard, not a filter, matching `fetch_screentime.implausible()`

### Removed

- The sleep column. There is no night sleep data to show: `InBed` records stop 2024-09-20, sleep staging stops 2023-12-13, and the only two records since May 2026 are afternoon naps. The importers and `sleep.json` stay, so restoring the column is a one-line change once sleep tracking is on

### Changed

- `habits_daily.py` commits a habit file only if its own importer just wrote it. Previously it committed any change to those paths, so a hand-run import would have been auto-committed unreviewed

## 2.1.2 — 2026-08-23

### Added

- `scripts/import_shortcut_sleep.py` — merges sleep dropped into `iCloud Drive/habits/sleep/` by a scheduled iOS Shortcut. Apple Health has no API and no local store on the Mac (it syncs through CloudKit's private database, not as files), so the only route is a phone-side push; iCloud Drive is the one such surface readable without Full Disk Access. Reuses `import_health.sleep_days` and `union` so a night from a drop file and the same night from a Health export cannot disagree, and filters tagged `InBed`/`Awake` samples, which Apple files under the same sleep type as the asleep stages and which would otherwise overstate a night

### Changed

- `screentime_daily.py` becomes `habits_daily.py` and now collects screen time *and* sleep, independently — one failing does not stop the other — committing whichever habit files changed. The LaunchAgent is relabelled `com.owenmedeiros.habits`, logging to `~/Library/Logs/habits-daily.log`

## 2.1.1 — 2026-08-23

### Fixed

- iPhone screen time, which the previous release recorded as unusable. `read_biome` now parses the `SEGB` segments under `~/Library/Biome/streams/restricted/App.InFocus/` as protobuf records rather than sweeping the bytes for anything that decodes as a plausible timestamp. Three things were wrong, not one: `tombstone/` directories hold sync bookkeeping rather than usage and were being read as sessions; StandBy — the charging clock face — is logged like an app and was a third of the total; and a synced Apple Watch is indistinguishable from a synced iPhone by path alone. Real data now gives a 1.78 h/day median over 29 days, against the 18 h/day and 2033 dates the old heuristic produced
- `read_knowledge` catching only `sqlite3.OperationalError` when opening the database. A Full Disk Access denial raises the parent `DatabaseError`, so the one failure the FDA hint exists for produced an unhandled traceback instead

### Added

- `scripts/screentime_daily.py` and a `com.owenmedeiros.screentime` LaunchAgent — daily collection at 23:00, committing `screentime.json` to `main` only, path-limited and skipped mid-rebase. Runs under `/usr/bin/python3` so the Full Disk Access grant lands on that interpreter rather than on `/bin/sh` and every shell script with it

### Changed

- iPhone screen time is on by default; `--iphone` becomes `--no-iphone`. `implausible()` still gates every write

## 2.1.0 — 2026-08-23

### Added

- `/habits` page: five GitHub-style heatmaps (running, stretching, screen time, commits, sleep) as side-by-side vertical columns, newest week at the top, with a hover/tap tooltip showing that day's numbers and a summary table of totals and streaks
- `scripts/fetch_strava.py` — OAuth fetch for the running habit
- `scripts/fetch_github.py` — contribution calendar via the GitHub GraphQL API
- `scripts/fetch_screentime.py` — Mac and iPhone screen time from local `knowledgeC.db` and Biome data (Apple exposes no web API)
- `scripts/import_health.py` — stretching (from the Bend app) and sleep, in one pass over an Apple Health `export.zip`
- `scripts/backfill_stretching.py` and `scripts/bend-history.csv` — hand-recorded Bend sessions predating the Apple Health connection, which does not backfill
- `scripts/habits_common.py` — shared env parsing and merge-on-write habit file handling
- `.github/workflows/habits.yml` — nightly refresh of the Strava and GitHub habits, committing to `main` to trigger a deploy; warns and skips rather than failing when credentials are not yet configured
- Two years of running (227 days) and GitHub commit (273 days) history, plus three weeks of backfilled Bend sessions

### Changed

- `Base.astro` gains a `Habits` nav entry and an opt-in `wide` prop (52rem) used only by `/habits`
- `/habits` is the one page carrying client-side JS, for the heatmap tooltip

### Removed

- `habits-wip.md`, superseded by the implemented page

## 2.0.1 — 2026-07-25

### Removed

- budget.owenmedeiros.com and wedding.owenmedeiros.com links from the homepage "Live apps" section

## 2.0.0 — 2026-07-25

Complete rebuild: migrated from MyST/Jupyter Book on GitHub Pages to Astro on Cloudflare Workers.

### Added

- Astro static site with minimal single-column design (serif body, small sans-serif nav, dark-mode aware, no client-side JS)
- `src/layouts/Base.astro` (site shell + all global CSS) and `src/layouts/Md.astro` (markdown page wrapper)
- Cloudflare Workers deployment (`wrangler.jsonc`) serving `dist/` as static assets on the custom domain `owenmedeiros.com`
- "Live apps" section on the homepage linking grafana., budget., and wedding.owenmedeiros.com
- Redirects: `/contact` → `/about`, `/publications` → `/research`, `/thesis` → `/research`
- Custom 404 page
- KaTeX math rendering in markdown (remark-math + rehype-katex)

### Changed

- Content reorganized: Contact merged into About; Publications and both thesis abstracts combined into a single Research page; projects and maths pages ported to `src/pages/` with assets in `public/`
- Maths pages now show their figure at the top
- Homepage title changed to "Owen Medeiros — Technical Profile" and duplicate on-page name heading removed
- Publications converted from a `{cite}`-based bibliography to a static markdown list (sources kept in `references.bib`)
- TDGL animation GIF downscaled from 28 MB to 4.5 MB; QNN blog PDF (46 MB) split into two parts to fit the Workers 25 MiB asset limit

### Removed

- MyST/Jupyter Book tooling: `myst.yml`, `_toc.yml`, `_config.yml`, `requirements.txt`, `_build/`, `_static/`
- GitHub Pages deploy workflow (`.github/workflows/deploy.yml`) and `DEPLOYMENT.md`
- `old-html-site/` legacy site
