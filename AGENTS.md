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
- **Six pages carry JS**, deliberately and narrowly. `/habits` passes `wide` to `Base` for a 52rem column (five heatmaps do not fit in 42rem) and carries an `is:inline` script for the heatmap tooltip. The four `/maths` pages each load one file from `public/maths/`: `aperiodic-tiles.js` for the tiling builder, `euler-spiral.js` for the curve viewer, `bertrand-paradox.js` for the chord sampler, and `mandelbrot.js` for the escape-time viewer. None can be done without a canvas, and all four stay at 42rem. `/projects/tdgl-simulation` loads `public/projects/tdgl/viewer3d.js` for its 3-D scenes (asked for by Owen, 2026-10). The wide column remains `/habits` alone. One more page carries JS, outside Astro: `public/projects/tdgl/live/nbn-3d.html` is the live 3-D NbN simulator (WebGL2), a self-contained static page with its own inline styles and script, linked from `/projects/tdgl-simulation` (asked for by Owen, 2026-10-24). It is built in `omedeiro/nanowire_tdgl`'s interactive-simulator work and copied here whole; edit it there, not by hand. Every other page stays 42rem and JS-free — do not generalise any of these exceptions without asking.
- All six keep their CSS in `Base.astro`, scoped by a class prefix (`.habits-*`, `.tiling*`, `.euler*`, `.bertrand*`, `.mandel-*`, `.tdgl3d*`), rather than adding a per-page stylesheet. Each canvas viewer reads its palette back out of those custom properties with `getComputedStyle`, so light and dark are defined once, in the stylesheet.
- The TDGL scenes are the one viewer built on a library: plotly's gl3d partial bundle, **vendored** at `public/projects/tdgl/3d/plotly-gl3d.min.js` (plotly.js-gl3d-dist-min 4.1.1, MIT) rather than loaded from a CDN. Each `<figure class="tdgl3d">` is a plain rendered PNG until the reader presses *Explore in 3-D*; only then are the 1.7 MB bundle and the scene's JSON fetched, so the page costs nothing extra to read. The scene JSON comes from the plotly figures `docs/figures/gallery_3d/render.py` writes in `omedeiro/nanowire_tdgl`, with float64 arrays narrowed to float32; the tilted-field figure is split into one file per field direction so each gets the full 42rem. The moat-grid field-line scene repeats the vortex-core isosurface of `moats.json` inline (the gallery's `_iso_from` reference is resolved at export), so each JSON stands alone.
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

`/habits` renders one heatmap per habit from one JSON file per habit in `src/data/habits/`,
all sharing one shape: `{id, label, source, unit, updated_at, days: {"YYYY-MM-DD": {value, extra?}}}`.
`value` is numeric and is what the page buckets on. Every writer goes through
`habits_common.write_habit`, which **merges** into the existing file — load-bearing, since the
Apple sources keep only ~4 weeks. `tests/` enforces the contract and the merge; CI runs them.

| Habit | Script | Refresh |
|---|---|---|
| Running, Push-ups | `scripts/fetch_strava.py` | nightly, automatic (`habits.yml`) |
| Commits | `scripts/fetch_github.py` | nightly, automatic (`habits.yml`) |
| Stretching | `scripts/import_shortcut_stretching.py --payload-file` | automatic — the phone POSTs a `repository_dispatch` (`stretching.yml`) |
| Weight | `scripts/import_shortcut_weight.py --payload-file` | automatic — `repository_dispatch` of type `weight`; see `docs/withings-weight-shortcut.md` |
| Screen time | `scripts/fetch_screentime.py` | LaunchAgent, daily on the Mac |
| Sleep, Stretching (fallback) | `scripts/import_shortcut_sleep.py`, `scripts/import_shortcut_stretching.py` | LaunchAgent, from an iCloud Drive drop |
| Stretching, Sleep (bulk) | `scripts/import_health.py` | manual, after a Health export |

Load the `habits-data` skill before touching any of these. `docs/habits-pipeline.md` is the
architectural review; `docs/habits-setup.md` is the one-time setup (tokens, secrets, LaunchAgent,
Shortcuts). The data workflows commit to `main` by design — a path-scoped exception, for data only.

## Skills

- `habits-data` (`.claude/skills/habits-data/SKILL.md`) — the habits pipeline, the Apple data sources on disk, and the dead ends already searched.
- `release` (`.claude/skills/release/SKILL.md`) — the release ritual below, step by step, with the checks a PR must pass.

## Publications

`src/pages/research.md` holds a static publications list. `references.bib` and `scripts/fetch_scholar.py` are kept for regenerating entries; update the markdown manually when new papers appear.

## Release / PR workflow (agent-driven changes)

All non-trivial changes (content edits, new pages, config changes) follow this process:

1. **Branch** — never commit directly to `main`. Create `feature/<short-slug>` from an up-to-date `main`.
2. **Version bump** — update `"version"` in `package.json` (semver). **Default to a patch bump** for most changes (content tweaks, link/copy edits, asset updates). Use minor for new pages/features, major only for site-wide redesigns or migrations.
3. **Changelog** — add a `## x.y.z — YYYY-MM-DD` entry at the top of `CHANGELOG.md` with `### Added` / `### Changed` / `### Removed` subsections as applicable.
4. **Verify** — run `npm run build` and confirm it succeeds, `grep -rl katex-error dist/` prints nothing (a bad math fence does not fail the build), and `python3 -m unittest discover -s tests` passes. CI (`.github/workflows/ci.yml`) repeats all three plus `scripts/check_agent_env.py` on every PR.
5. **Commit** — one commit including the change, version bump, and changelog. Concise imperative subject line.
6. **PR** — push the branch and open a PR with `gh pr create` (summary of what/why). The `release` skill has the full ritual.
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
