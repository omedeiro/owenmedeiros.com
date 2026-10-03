// Interactive 3-D scenes on /projects/tdgl-simulation.
//
// Each <figure class="tdgl3d"> starts as a plain rendered image, so the page
// reads without JavaScript and loads nothing heavy up front. Pressing
// "Explore in 3-D" loads plotly's gl3d bundle (once, shared by every figure)
// and the scene's JSON, and swaps the image for a live plot. Colours come
// from the --fg / --muted / --border custom properties in Base.astro, so the
// plot follows the light and dark palettes without repeating them here.

(function () {
  const PLOTLY_SRC = "/projects/tdgl/3d/plotly-gl3d.min.js";
  let plotlyPromise = null;

  function loadPlotly() {
    if (window.Plotly) return Promise.resolve(window.Plotly);
    if (!plotlyPromise) {
      plotlyPromise = new Promise((resolve, reject) => {
        const s = document.createElement("script");
        s.src = PLOTLY_SRC;
        s.async = true;
        s.onload = () => resolve(window.Plotly);
        s.onerror = () => {
          plotlyPromise = null;
          reject(new Error("could not load the 3-D library"));
        };
        document.head.appendChild(s);
      });
    }
    return plotlyPromise;
  }

  const figCache = new Map();
  function loadFigure(src) {
    if (!figCache.has(src)) {
      figCache.set(
        src,
        fetch(src).then((r) => {
          if (!r.ok) throw new Error(`could not load ${src} (${r.status})`);
          return r.json();
        }),
      );
    }
    return figCache.get(src).catch((e) => {
      figCache.delete(src);
      throw e;
    });
  }

  function themedLayout(fig, el, dragmode) {
    const css = getComputedStyle(el);
    const fg = css.getPropertyValue("--fg").trim();
    const muted = css.getPropertyValue("--muted").trim();
    const border = css.getPropertyValue("--border").trim();
    const lay = JSON.parse(JSON.stringify(fig.layout));
    lay.paper_bgcolor = "rgba(0,0,0,0)";
    lay.font = {
      family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif',
      size: 11,
      color: fg,
    };
    lay.autosize = true;
    lay.margin = { l: 0, r: 0, t: 0, b: 0 };
    if (lay.legend) {
      lay.legend.bgcolor = "rgba(0,0,0,0)";
      lay.legend.font = { color: fg, size: 11 };
      lay.legend.x = 0;
      lay.legend.y = 1;
    }
    // The scenes were framed for a wide page; on a phone the same camera crops
    // the device, so pull it back in proportion to the lost width.
    const pullBack = Math.min(1.8, Math.max(1, 560 / Math.max(el.clientWidth, 1)));
    for (const k of Object.keys(lay)) {
      if (!k.startsWith("scene")) continue;
      lay[k].dragmode = dragmode;
      const eye = lay[k].camera && lay[k].camera.eye;
      if (eye) for (const a of ["x", "y", "z"]) eye[a] *= pullBack;
      for (const a of ["xaxis", "yaxis", "zaxis"]) {
        if (!lay[k][a]) continue;
        Object.assign(lay[k][a], {
          gridcolor: border,
          zerolinecolor: border,
          color: muted,
          tickfont: { size: 10, color: muted },
        });
      }
    }
    return lay;
  }

  function themedData(fig, el) {
    const fg = getComputedStyle(el).getPropertyValue("--fg").trim();
    return fig.data.map((t) => {
      if (!t.colorbar) return t;
      const c = Object.assign({}, t.colorbar, {
        tickfont: { size: 10, color: fg },
        len: 0.45,
        thickness: 10,
        x: 1,
        xanchor: "right",
      });
      if (c.title) c.title = Object.assign({}, c.title, { font: { size: 11, color: fg } });
      return Object.assign({}, t, { colorbar: c });
    });
  }

  function button(label, onClick, pressed) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = label;
    if (pressed !== undefined) b.setAttribute("aria-pressed", String(pressed));
    b.addEventListener("click", onClick);
    return b;
  }

  function setup(figure) {
    const stage = figure.querySelector(".tdgl3d-stage");
    const controls = figure.querySelector(".tdgl3d-controls");
    const poster = stage.innerHTML;
    let scenes;
    try {
      scenes = JSON.parse(figure.dataset.scenes);
    } catch (e) {
      return;
    }

    let current = 0;
    let dragmode = "orbit";
    let plot = null;
    let fig = null;

    function draw() {
      if (!plot || !fig) return;
      window.Plotly.react(plot, themedData(fig, figure), themedLayout(fig, figure, dragmode), {
        responsive: true,
        displaylogo: false,
        displayModeBar: false,
      });
    }

    function fail(e) {
      stage.innerHTML = poster;
      const p = document.createElement("p");
      p.className = "tdgl3d-error";
      p.textContent = `The 3-D view could not start here (${e.message}); the image above shows the same scene.`;
      stage.appendChild(p);
      plot = null;
      showIdle();
    }

    function open(i) {
      current = i;
      figure.classList.add("is-loading");
      Promise.all([loadPlotly(), loadFigure(scenes[i].src)])
        .then(([, data]) => {
          fig = data;
          if (!plot) {
            stage.innerHTML = "";
            plot = document.createElement("div");
            plot.className = "tdgl3d-plot";
            plot.setAttribute("role", "img");
            plot.setAttribute("aria-label", `${figure.dataset.title || "3-D scene"}, interactive`);
            stage.appendChild(plot);
          } else {
            window.Plotly.purge(plot);
          }
          draw();
          showLive();
        })
        .catch(fail)
        .finally(() => figure.classList.remove("is-loading"));
    }

    function close() {
      if (plot) window.Plotly.purge(plot);
      plot = null;
      stage.innerHTML = poster;
      showIdle();
    }

    function showIdle() {
      controls.replaceChildren(button("Explore in 3-D", () => open(current)));
    }

    function showLive() {
      const row = [];
      if (scenes.length > 1) {
        const group = document.createElement("span");
        group.className = "tdgl3d-group";
        scenes.forEach((s, i) => group.appendChild(button(s.label, () => open(i), i === current)));
        row.push(group);
      }
      const modes = document.createElement("span");
      modes.className = "tdgl3d-group";
      for (const [label, m] of [
        ["Rotate", "orbit"],
        ["Pan", "pan"],
      ]) {
        modes.appendChild(
          button(
            label,
            () => {
              dragmode = m;
              modes.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b.textContent === label)));
              const upd = {};
              for (const k of Object.keys(plot.layout || {})) if (k.startsWith("scene")) upd[k + ".dragmode"] = m;
              window.Plotly.relayout(plot, upd);
            },
            dragmode === m,
          ),
        );
      }
      row.push(modes);
      row.push(button("Reset view", () => { window.Plotly.purge(plot); draw(); }));
      row.push(button("Back to image", close));
      controls.replaceChildren(...row);
    }

    controls.hidden = false;
    showIdle();
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", draw);
  }

  document.querySelectorAll("figure.tdgl3d").forEach(setup);
})();
