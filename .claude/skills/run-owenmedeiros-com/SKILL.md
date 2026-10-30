---
name: run-owenmedeiros-com
description: Build, run, and drive the owenmedeiros.com Astro site in a headless browser. Use when asked to start or preview the site, build it, take a screenshot of a page, check a page in dark mode or at phone width, poke the canvas viewers (/maths), the /habits heatmaps, the TDGL 3-D scenes or the live WebGL simulator, or confirm a change works in the rendered site rather than just in `npm run build`.
---

A static Astro site. Build it, serve `dist/` with `astro preview`, then drive pages with
`.claude/skills/run-owenmedeiros-com/driver.mjs`: a Playwright script that reads one command per line
from stdin, prints what happened, saves screenshots, and exits 1 if anything threw, logged a console
error, or a request failed. All paths below are relative to the repo root.

## Prerequisites

Nothing to install with apt. The cloud container already has Node 22, `git-lfs`, and Playwright with
Chromium (globally, on `NODE_PATH`); the driver finds it there, so this repo needs no Playwright
dependency.

## Setup and build

```bash
npm ci
git lfs pull          # only if you need the real PDFs; a fresh clone has 133-byte pointer files
npm run build         # ~4 s, 19 pages into dist/
grep -rl katex-error dist   # must print nothing: a broken $$ fence still exits 0 (see AGENTS.md)
```

## Run (agent path)

Serve the build and wait for the port:

```bash
npm run preview -- --port 4321 > /tmp/preview.log 2>&1 &
timeout 30 bash -c 'until curl -sf localhost:4321/ >/dev/null; do sleep 0.5; done'
```

Drive it. This is the flow verified in this container, touching each JS-carrying page:

```bash
node .claude/skills/run-owenmedeiros-com/driver.mjs <<'EOF'
nav /
ss home
nav /maths/euler-spiral/
wait .katex
eval getComputedStyle(document.querySelector('.katex')).fontFamily
nav /maths/mandelbrot/
wait canvas
ss-el canvas mandel-before
wheel canvas -600
drag canvas 120 40
sleep 800
ss-el canvas mandel-after
nav /habits/
hover .habits-cell >> nth=200
eval document.querySelector('.habits-tip').hidden + ' | ' + document.querySelector('.habits-tip').textContent
nav /projects/tdgl-simulation/
click figure.tdgl3d button
wait figure.tdgl3d .js-plotly-plot
sleep 1500
ss-el figure.tdgl3d tdgl3d
nav /projects/tdgl/live/nbn-3d.html
sleep 4000
eval typeof sim !== 'undefined' && sim ? {t: sim.t, lost: sim.gl.isContextLost()} : 'no sim'
viewport 390 844
nav /
ss home-phone
scheme dark
nav /
ss home-dark
errors
EOF
echo exit=$?
```

Screenshots land in `/tmp/owenmedeiros-shots/<name>.png` (override with `SHOTS=dir`). **Open them and
look**; exit 0 only means nothing errored. Point at another server with `BASE=http://localhost:4322`,
or `nav` a full `https://owenmedeiros.com/...` URL to check production.

| command | does |
|---|---|
| `nav <path\|url>` | load and wait for `load`; prints status, final URL, title |
| `wait <sel>` / `text <sel>` | wait 10 s for visible / print innerText |
| `click <sel>` / `hover <sel>` / `fill <sel> <text>` / `press <key>` | input (Playwright selectors, so `>> nth=3` works) |
| `drag <sel> <dx> <dy>` / `wheel <sel> <dy>` | pan / zoom a canvas viewer (negative `dy` zooms in) |
| `eval <js>` | print the expression's value as JSON |
| `sleep <ms>` | let an animation or the WebGL solver run |
| `ss [name]` / `ss-el <sel> [name]` | full-page / single-element screenshot |
| `viewport <w> <h>` | resize the current page (390 844 = phone) |
| `scheme <light\|dark>` | new context in that colour scheme; `nav` again after |
| `errors` | print every console error, page error, failed or >= 400 request so far |

Stop the server: `lsof -ti:4321 -sTCP:LISTEN | xargs -r kill`

### Live simulator on WebGL backends

`scripts/webgl-check/check.mjs` is the repo's own deeper check of `nbn-3d.html` (runs ~60 s, steps the
solver, fires a photon, writes `webgl-<backend>.png`, gitignored). CI runs it on Windows; on Linux
only `swiftshader` applies, pointed at the bundled Chromium:

```bash
npm install --no-save playwright-core@1.49.1
CHROME_PATH=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome node scripts/webgl-check/check.mjs swiftshader
```

Last line `[swiftshader] OK` is a pass.

## Run (human path)

`npm run dev` serves with hot reload on 4321. Under an agent it does not stay in the foreground (next
gotcha), so the driver flow above uses `preview` against a fresh build.

## Test

There is no test suite. `npm run build` plus the `katex-error` grep is the check AGENTS.md asks for;
the driver flow above is the rendered check.

## Gotchas

- **`astro dev` backgrounds itself when not on a TTY.** Astro 7 prints JSON `Dev server running ...
  (pid N)` and returns exit 0 in about a second; the server keeps running detached. Manage it with
  `npx astro dev status`, `npx astro dev logs`, `npx astro dev stop`. If you kill it by port instead,
  `status` then reports nothing running. `preview` behaves normally with `&`.
- **KaTeX's CSS comes from cdn.jsdelivr.net, which this container's egress proxy refuses** (403 on
  CONNECT, `net::ERR_TUNNEL_CONNECTION_FAILED` in Chromium). The driver intercepts those requests and
  serves `node_modules/katex/dist/` instead (installed by rehype-katex, version 0.16.4x vs the 0.16.11
  the pages name), so math renders properly and `errors` stays clean. `CDN=live` turns that off.
  `curl` to jsdelivr fails the same way, so this is not a driver bug.
- **WebGL2 works headless.** The driver launches Chromium with `--enable-unsafe-swiftshader`; the live
  simulator reports `ANGLE (Google, Vulkan 1.3.0 (SwiftShader ...))`, passes its own GPU check and
  advances `sim.t` (~3 ps after 4 s). Slow, but real.
- **`npm install --no-save --no-package-lock ...` (the CI line for webgl-check) silently upgrades
  astro** to the newest ^7 (7.1.3 -> 7.4.1 here), since it ignores the lockfile. Drop
  `--no-package-lock` locally, or re-run `npm ci` afterwards.
- **PDFs are Git LFS pointers after clone.** `/projects/...pdf` links serve 133-byte text files until
  `git lfs pull`, which works through the proxy here.
- **Redirects are static pages.** `/contact`, `/publications`, `/thesis` return 200 with a
  meta-refresh, not a 301, under `preview` (Cloudflare does the same with the built files). `nav`
  follows them, so check `page.url()` in the printed line.
- **`/habits` has ~17,000 `.habits-cell` elements**, so a bare `hover .habits-cell` hits the first,
  often an empty pad cell. Pick one with `>> nth=N`; the tooltip is `.habits-tip`, unhidden on hover.
- **TDGL 3-D scenes are images until clicked.** `figure.tdgl3d button` is *Explore in 3-D*; only then
  do the 1.7 MB plotly bundle and scene JSON load. Wait for `.js-plotly-plot` before screenshotting.

## Troubleshooting

- **`requestfailed: https://cdn.jsdelivr.net/... net::ERR_TUNNEL_CONNECTION_FAILED`**: run with
  `CDN=live` or an old driver; the egress policy blocks jsdelivr. Use the driver's default.
