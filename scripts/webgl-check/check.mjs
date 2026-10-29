// Loads the live 3-D simulator in the installed Chrome with a given ANGLE backend and prints what a
// visitor would see: WebGL renderer, errors, the GPU check, whether the solver advances and the view draws.
// Usage: node scripts/webgl-check/check.mjs <angle backend: default|d3d11|d3d11-warp|gl|vulkan|swiftshader> [page URL]
// With no URL it serves this checkout's public/ folder; pass https://owenmedeiros.com/... to check the live site.
import { chromium } from 'playwright-core';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';

const backend = process.argv[2] || 'default', url = process.argv[3] || '';
const root = path.resolve('public');
const types = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.png': 'image/png' };
const server = http.createServer((req, res) => {
  const f = path.join(root, decodeURIComponent(req.url.split('?')[0]));
  if (!f.startsWith(root) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { 'content-type': types[path.extname(f)] || 'application/octet-stream' }); fs.createReadStream(f).pipe(res);
}).listen(0);
const port = server.address().port;

// Chrome's own log (ANGLE writes the Direct3D shader compiler's errors there) and the translated HLSL of the
// shaders, for when a draw fails
const logFile = path.resolve(`chrome-${backend}.log`);
const args = ['--ignore-gpu-blocklist', '--enable-unsafe-swiftshader', '--enable-logging', `--log-file=${logFile}`, '--v=0', '--enable-privileged-webgl-extensions'];
if (backend !== 'default') args.push('--use-gl=angle', `--use-angle=${backend}`);
const problems = [];
const browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH, headless: true, args } : { channel: 'chrome', headless: true, args });
const log = (...a) => console.log(`[${backend}${url ? ' live' : ''}]`, ...a);
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
  // name the program behind any draw that loses the context: each draw is followed by getError (a sync point)
  await page.addInitScript(() => {
    const P = WebGL2RenderingContext.prototype, src = new WeakMap(), att = new WeakMap(); let cur = null, n = 0;
    const ss = P.shaderSource; P.shaderSource = function (sh, s) { src.set(sh, s); return ss.call(this, sh, s); };
    const as = P.attachShader; P.attachShader = function (p, sh) { if (this.getShaderParameter(sh, this.SHADER_TYPE) === this.FRAGMENT_SHADER) att.set(p, src.get(sh)); return as.call(this, p, sh); };
    const up = P.useProgram; P.useProgram = function (p) { cur = p; return up.call(this, p); };
    for (const f of ['drawArrays', 'drawElements']) {
      const d = P[f]; P[f] = function (...a) {
        const r = d.apply(this, a); n++;
        if (!window.__glBad && (this.getError() || this.isContextLost())) {
          const s = (cur && att.get(cur)) || '';
          let hlsl = ''; try { const x = this.getExtension('WEBGL_debug_shaders'), sh = this.getAttachedShaders(cur).find(q => this.getShaderParameter(q, this.SHADER_TYPE) === this.FRAGMENT_SHADER); hlsl = x && sh ? x.getTranslatedShaderSource(sh) : 'no WEBGL_debug_shaders'; } catch (e) { hlsl = 'translated source unavailable: ' + e.message; }
          window.__glHlsl = hlsl;
          window.__glBad = { draw: n, lost: this.isContextLost(), outs: (s.match(/layout\s*\(\s*location[^;]*out[^;]*;/g) || []).join(' '), main: s.replace(/\s+/g, ' ').slice(-1500) };
          console.error('first failing draw #' + n + ': ' + JSON.stringify(window.__glBad));
        }
        return r;
      };
    }
  });
  page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') log('console.' + m.type() + ':', m.text()); });
  page.on('pageerror', e => { log('pageerror:', e.message); problems.push('page error: ' + e.message); });
  page.on('crash', () => { log('PAGE CRASHED'); problems.push('page crashed'); });
  await page.goto(url || `http://localhost:${port}/projects/tdgl/live/nbn-3d.html`);
  const probe = () => page.evaluate(() => {
    const t = id => { const e = document.getElementById(id); return e && !e.hidden ? e.textContent.trim().slice(0, 200) : ''; };
    let gl = null; try { gl = typeof sim !== 'undefined' && sim && sim.gl; } catch (e) {}
    const lost = gl ? gl.isContextLost() : null;
    return {
      t: typeof sim !== 'undefined' && sim ? +sim.t.toFixed(1) : null, lost,
      scale: typeof scale !== 'undefined' ? scale : null, perFrame: typeof perFrame !== 'undefined' ? perFrame : null,
      gpu: typeof gpuName === 'function' ? (() => { try { return gpuName(); } catch (e) { return 'gpuName threw ' + e.message; } })() : null,
      noGl: t('noGl'), err: t('errBox'), check: t('checkNote'), state: t('rT'),
    };
  });
  let at = 0;
  for (const s of [3, 10, 25, 45]) {
    await page.waitForTimeout((s - at) * 1000); at = s;
    log(`after ~${s}s`, JSON.stringify(await probe()));
  }
  // field lines on, then a photon on the film
  await page.evaluate(() => { const b = document.getElementById('linesBtn'); if (b) b.click(); });
  await page.waitForTimeout(5000);
  log('field lines', JSON.stringify(await page.evaluate(() => ({ n: lines.paths.length, on: lines.on }))));
  const box = await page.locator('#view').boundingBox();
  if (box) await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  await page.waitForTimeout(10000);
  log('after photon', JSON.stringify(await probe()));
  // the photon-event preset (the thin-film SNSPD wire, its own solver mode), where the page has it
  const hasPh = await page.evaluate(() => { const b = document.getElementById('photonBtn'); if (b) b.click(); return !!b; });
  if (hasPh) { await page.evaluate(() => { nextShot = 0; }); await page.waitForTimeout(15000);
    log('photon event', JSON.stringify(await page.evaluate(() => ({ size: [sim.nx, sim.ny, sim.nz], frozen: sim.frozen, t: +sim.t.toFixed(1), state: document.getElementById('rState').textContent, Tf: document.getElementById('rTf').textContent })))); }
  const end = await probe();
  log('end', JSON.stringify(end));
  if (end.noGl) problems.push('no-WebGL overlay: ' + end.noGl);
  if (end.err) problems.push('error box: ' + end.err);
  if (end.lost) problems.push('WebGL context lost');
  if (!(end.t > 1)) problems.push(`solver did not advance (t = ${end.t})`);
  if (/could not run/.test(end.check)) problems.push(end.check);
  log('canvas', JSON.stringify(await page.evaluate(() => { const c = document.getElementById('view'); return { buffer: [c.width, c.height], css: [c.clientWidth, c.clientHeight] }; })));
  await page.screenshot({ path: `webgl-${backend}${url ? '-live' : ''}.png` });
  const hlsl = await page.evaluate(() => window.__glHlsl || '');
  if (hlsl) { fs.writeFileSync(`shader-${backend}.hlsl`, hlsl); log(`translated shader saved (${hlsl.length} chars)`); }
} catch (e) { problems.push('check script: ' + e.message); }
finally { await browser.close(); server.close(); }
try { // the browser's log lines about shaders and the GPU
  const lines = fs.readFileSync(logFile, 'utf8').split(/\r?\n/).filter(l => /error X|warning X|HLSL|compil|D3D11|shader|lost/i.test(l));
  if (lines.length) log('chrome log:\n' + lines.slice(0, 60).join('\n'));
} catch (e) { log('no chrome log: ' + e.message); }
if (problems.length) { console.log(`::error::${backend}${url ? ' live' : ''}: ` + problems.join(' | ')); process.exit(1); }
log('OK');
