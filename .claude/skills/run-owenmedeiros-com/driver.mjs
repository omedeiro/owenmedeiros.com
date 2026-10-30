// Headless-Chromium driver for owenmedeiros.com. Reads one command per line from stdin (or from a file
// given as the first argument), runs them against a page, and prints what happened.
//
//   node .claude/skills/run-owenmedeiros-com/driver.mjs <<'EOF'
//   nav /maths/mandelbrot/
//   wait canvas
//   ss mandelbrot
//   EOF
//
// Paths in `nav` are relative to $BASE (default http://localhost:4321, the `npm run preview` port).
// Screenshots go to $SHOTS (default /tmp/owenmedeiros-shots, outside the repo).
// Exits 1 if the page threw, logged a console error, or any request failed or returned >= 400.
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';

// playwright is installed globally in the container (NODE_PATH), not in this repo; ESM `import` ignores
// NODE_PATH, so resolve it through require.
const require = createRequire(import.meta.url);
let chromium;
try { ({ chromium } = require('playwright')); }
catch { ({ chromium } = require(path.join(process.env.NODE_PATH || '/usr/local/lib/node_modules_global', 'playwright'))); }

const BASE = (process.env.BASE || 'http://localhost:4321').replace(/\/$/, '');
const SHOTS = path.resolve(process.env.SHOTS || '/tmp/owenmedeiros-shots');
fs.mkdirSync(SHOTS, { recursive: true });

const src = process.argv[2] ? fs.readFileSync(process.argv[2], 'utf8') : fs.readFileSync(0, 'utf8');
const lines = src.split('\n').map(l => l.trim()).filter(l => l && !l.startsWith('#'));

const problems = [];
const browser = await chromium.launch({ args: ['--no-sandbox', '--ignore-gpu-blocklist', '--enable-unsafe-swiftshader'] });
let context, page;
async function open(opts = {}) {
  if (context) await context.close();
  context = await browser.newContext({ viewport: { width: 1280, height: 900 }, ...opts });
  // The pages pull KaTeX's stylesheet (and its fonts) from cdn.jsdelivr.net, which this container's egress
  // policy refuses. Serve them from the katex copy rehype-katex already installed, so math renders as on the
  // live site instead of as unstyled spans. Set CDN=live to let the request go out as-is.
  if (process.env.CDN !== 'live') await context.route(/^https:\/\/cdn\.jsdelivr\.net\/npm\/katex@[^/]+\/dist\//, route => {
    const f = path.resolve('node_modules/katex/dist', new URL(route.request().url()).pathname.replace(/^.*?\/dist\//, ''));
    fs.existsSync(f) ? route.fulfill({ path: f }) : route.abort();
  });
  page = await context.newPage();
  page.on('console', m => { if (m.type() === 'error') { problems.push('console.error: ' + m.text()); console.log('  console.error:', m.text()); } });
  page.on('pageerror', e => { problems.push('pageerror: ' + e.message); console.log('  pageerror:', e.message); });
  page.on('requestfailed', r => { problems.push(`requestfailed: ${r.url()} ${r.failure()?.errorText}`); console.log('  requestfailed:', r.url(), r.failure()?.errorText); });
  page.on('response', r => { if (r.status() >= 400) { problems.push(`HTTP ${r.status()}: ${r.url()}`); console.log(`  HTTP ${r.status()}:`, r.url()); } });
}
await open();

let n = 0;
const shot = name => path.join(SHOTS, `${name || String(++n).padStart(2, '0')}.png`);
const url = p => /^https?:/.test(p) ? p : BASE + (p.startsWith('/') ? p : '/' + p);

const cmds = {
  // nav <path|url>          load a page and wait for the load event
  nav: async p => { const r = await page.goto(url(p), { waitUntil: 'load' }); console.log(`  ${r.status()} ${page.url()}  title="${await page.title()}"`); },
  // wait <selector>         wait (10 s) for an element to be visible
  wait: async s => { await page.locator(s).first().waitFor({ timeout: 10000 }); },
  // text <selector>         print an element's innerText (first 400 chars)
  text: async s => console.log('  ' + (await page.locator(s).first().innerText()).slice(0, 400).replace(/\n/g, '\n  ')),
  // click <selector>
  click: async s => { await page.locator(s).first().click(); },
  // hover <selector>        e.g. a /habits heatmap cell, to raise its tooltip
  hover: async s => { await page.locator(s).first().hover(); },
  // fill <selector> <text>
  fill: async a => { const [s, ...t] = a.split(' '); await page.locator(s).first().fill(t.join(' ')); },
  // press <key>             e.g. Enter, ArrowLeft
  press: async k => { await page.keyboard.press(k); },
  // drag <selector> <dx> <dy>   mouse-drag from the element's centre (pans the canvas viewers)
  drag: async a => {
    const [s, dx, dy] = a.split(' '); const b = await page.locator(s).first().boundingBox();
    const x = b.x + b.width / 2, y = b.y + b.height / 2;
    await page.mouse.move(x, y); await page.mouse.down(); await page.mouse.move(x + +dx, y + +dy, { steps: 10 }); await page.mouse.up();
  },
  // wheel <selector> <dy>   scroll-wheel over the element's centre (negative zooms in on the canvas viewers)
  wheel: async a => {
    const [s, dy] = a.split(' '); const b = await page.locator(s).first().boundingBox();
    await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2); await page.mouse.wheel(0, +dy);
  },
  // eval <js expression>    print the result, JSON-encoded
  eval: async js => console.log('  =>', JSON.stringify(await page.evaluate(js))),
  // sleep <ms>              let an animation or a WebGL solver run
  sleep: async ms => page.waitForTimeout(+ms),
  // ss [name]               full-page screenshot to $SHOTS/<name>.png
  ss: async name => { const f = shot(name); await page.screenshot({ path: f, fullPage: true }); console.log('  saved', f); },
  // ss-el <selector> [name] screenshot of one element
  'ss-el': async a => { const [s, name] = a.split(' '); const f = shot(name); await page.locator(s).first().screenshot({ path: f }); console.log('  saved', f); },
  // viewport <w> <h>        e.g. `viewport 390 844` for a phone; keeps the current page
  viewport: async a => { const [w, h] = a.split(' ').map(Number); await page.setViewportSize({ width: w, height: h }); },
  // scheme <light|dark>     fresh context in that colour scheme (navigate again afterwards)
  scheme: async s => open({ colorScheme: s }),
  // errors                  print everything collected so far
  errors: async () => console.log(problems.length ? problems.map(p => '  ' + p).join('\n') : '  (none)'),
};

let failed = false;
for (const line of lines) {
  const i = line.indexOf(' '), cmd = i < 0 ? line : line.slice(0, i), arg = i < 0 ? '' : line.slice(i + 1).trim();
  console.log('> ' + line);
  if (!cmds[cmd]) { console.log(`  unknown command "${cmd}"; known: ${Object.keys(cmds).join(' ')}`); failed = true; break; }
  try { await cmds[cmd](arg); }
  catch (e) { console.log('  FAILED:', e.message.split('\n')[0]); failed = true; break; }
}
await browser.close();
if (problems.length) console.log(`${problems.length} problem(s) seen; see above`);
process.exit(failed || problems.length ? 1 : 0);
