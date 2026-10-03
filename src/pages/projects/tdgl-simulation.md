---
layout: ../../layouts/Md.astro
title: TDGL Simulation
description: tdgl3d, a fully 3-D superconducting circuit simulator built on the time-dependent Ginzburg–Landau equations, with vortex dynamics, transport current, self-heating, and inductance and capacitance extraction. Includes interactive 3-D scenes.
---

tdgl3d is a fully three-dimensional simulator for superconducting devices and
circuits, built on the time-dependent Ginzburg–Landau (TDGL) equations. It
resolves what circuit models leave out: where vortices enter, how they move under
a bias current, where they dissipate, and how much the film heats. Stacked
metal–insulator–metal layers, holes, notches and the vacuum around the conductor
are all on one 3-D grid, so the third dimension is part of the physics rather than
an extrusion of a 2-D film.

The order parameter ψ and the gauge field live on a structured finite-difference
grid, with **A** stored as link variables (Peierls phases) on the edges so that
gauge invariance and flux quantisation hold exactly on the lattice rather than
approximately.

$$
\frac{\partial \psi}{\partial t} = (\nabla - i\mathbf{A})^2 \psi + (1 - |\psi|^2)\,\psi
$$

$$
\frac{\partial \mathbf{A}}{\partial t} = \kappa^2 \nabla \times (\nabla \times \mathbf{A}) - \mathrm{Im}\!\left[\psi^* (\nabla - i\mathbf{A})\psi\right]
$$

Everything is dimensionless: lengths in coherence lengths ξ, fields in $B_{c2}$.
Three numbers fix the normalisation — $\Phi_0 = 2\pi$, $\lambda = \kappa$ (in ξ),
and $H_{c2} = 1$. Devices drawn in SI units are converted with ξ taken at the
temperature of interest.

## What it simulates

- **Vortex dynamics in 3-D** — entry, pinning on holes, lattice formation and flux
  flow, with vortex lines free to bend and tilt through the thickness.
- **Heterostructures** — S/I/S stacks, inclusions, etched (vacuum) holes and
  regions of locally suppressed $T_c$, coupled only through the field.
- **Transport current** — normal-metal terminals inject current, with the
  electric potential solved at every step. Either the film is thin and does not
  screen (pyTDGL's limit), or the current's own magnetic field is carried
  self-consistently.
- **Self-heating** — a heat equation driven by the TDGL dissipation feeds back
  through the local temperature, so a hotspot can switch a wire and latch it
  normal.
- **Circuit parameters** — kinetic and geometric inductance per unit length and
  small-signal AC impedance from a TDGL run, a static London solver for the
  port inductance matrix of 3-D wiring, and a 2-D electrostatic solve for
  capacitance, giving $Z_0$ and phase velocity.
- **A service around it** — every capability is described by a versioned
  project schema and runs as a job behind a FastAPI server, so a UI or an AI
  assistant drives the same simulations as a script.

## In three dimensions

Four runs where the thickness and the vacuum around the conductor change the
answer. Each starts as a rendered image; **Explore in 3-D** loads the scene
itself, which can be rotated, panned and zoomed, and a legend entry clicked to
hide a layer.

<figure class="tdgl3d" data-title="S/I/S stack in vacuum" data-scenes='[{"label":"Stack","src":"/projects/tdgl/3d/trilayer.json"}]'>
  <div class="tdgl3d-stage"><a href="/projects/tdgl/3d/sis-stack.png"><img src="/projects/tdgl/3d/sis-stack.png" alt="Cut-away S/I/S stack in a perpendicular field, with field lines bending around it and the screening current on the top face" loading="lazy" /></a></div>
  <div class="tdgl3d-controls" hidden></div>
  <figcaption>An S/I/S stack — two 3 ξ metal layers around a 1 ξ insulator, 16 ξ square, with 5 ξ of vacuum on every side — in a perpendicular field, cut away so the layers show in section. Field lines are coloured by |B| over the applied field: the metal screens it to 4.7% at the centre, and the expelled flux crowds past the edges at up to 1.36 times the applied field.</figcaption>
</figure>

<figure class="tdgl3d" data-title="Vortices in a tilted field" data-scenes='[{"label":"Field along the normal","src":"/projects/tdgl/3d/tilted-0.json"},{"label":"Tilted 45°","src":"/projects/tdgl/3d/tilted-45.json"}]'>
  <div class="tdgl3d-stage"><a href="/projects/tdgl/3d/tilted-vortices.png"><img src="/projects/tdgl/3d/tilted-vortices.png" alt="Vortex cores in a 3 ξ film: upright with the field along the normal, leaning with the field tilted 45 degrees" loading="lazy" /></a></div>
  <div class="tdgl3d-controls" hidden></div>
  <figcaption>An 18 × 18 × 3 ξ platelet quenched in a field along its normal and tilted 45°. Orange surfaces are the vortex cores (|ψ| = 0.4). With the field tilted, the mean field inside the film leans 47° but the cores lean only 29° ± 5°: the film is thinner than 2λ, so most of the in-plane field passes through as a smooth London field and the cores stay short. A 2-D film cannot show this; its cores are perpendicular by construction.</figcaption>
</figure>

<figure class="tdgl3d" data-title="Flux flow in a thick strip" data-scenes='[{"label":"Flux flow","src":"/projects/tdgl/3d/flow.json"}]'>
  <div class="tdgl3d-stage"><a href="/projects/tdgl/3d/flux-flow.png"><img src="/projects/tdgl/3d/flux-flow.png" alt="A 3 ξ thick strip carrying current, with vortex tubes crossing it and current streamlines wrapping each core" loading="lazy" /></a></div>
  <div class="tdgl3d-controls" hidden></div>
  <figcaption>A 24 × 10 × 3 ξ strip carrying transport current with its own field included, in B<sub>z</sub> = 0.5 H<sub>c2</sub>. About twelve vortex tubes cross it at a time, straight through the thickness to within a grid cell; new ones enter through the far edge pinched at mid-thickness. Streamlines show the current on the mid-plane, coloured by |J|.</figcaption>
</figure>

<figure class="tdgl3d" data-title="Field-cooled ground plane with moats" data-scenes='[{"label":"Vortex cores","src":"/projects/tdgl/3d/moats.json"},{"label":"Currents","src":"/projects/tdgl/3d/moats-current.json"},{"label":"Field lines","src":"/projects/tdgl/3d/moats-field.json"}]'>
  <div class="tdgl3d-stage"><a href="/projects/tdgl/3d/moat-grid.png"><img src="/projects/tdgl/3d/moat-grid.png" alt="An S/I/S ground plane with a 3 by 3 grid of square moats, with orange vortex columns running through both metal layers and field lines through the cores and moats" loading="lazy" /></a></div>
  <div class="tdgl3d-controls" hidden></div>
  <figcaption>A 36 ξ square S/I/S ground plane (3 ξ metal, 1 ξ oxide, 3 ξ metal) with nine 4 ξ moats etched through it, cooled through T<sub>c</sub> in B<sub>z</sub> = 0.25 H<sub>c2</sub>, about 52 flux quanta. The two layers share no Josephson coupling and start from independent random states, yet 16 of the bottom layer's 18 film vortices end up stacked under one in the top layer. Each layer holds 39 quanta: the bottom keeps two more in the film, the top holds those two in its moats. <em>Currents</em> cuts along the middle row of moats to show |J| in each layer, ringing every core and moat rim. <em>Field lines</em> carries equal flux per line over a map of B<sub>z</sub> in the top metal: λ = 2 ξ against a 5 ξ vortex spacing keeps the field between 0.74 and 1.21 of the applied value.</figcaption>
</figure>

## A 3×3 array of 4 µm holes

The coherence length fixes the grid spacing, but fabrication fixes the device, so a
real hole array is a large simulation: nine 4 µm holes on an 8 µm pitch with an 8 µm
buffer is 36 µm across, and at ξ = 150 nm that is 240 × 240 × 9 — 457 k nodes. At
ξ = 50 nm it is 15 M nodes in 12 GB.

The obvious way to get flux into the holes does not work, and that is the
interesting part. Ramping the field up, nothing enters until 3.15 mT — and just
above that, hundreds of vortices enter at once. Held at 3.6 mT, 567 of them pack
the buffer into a triangular lattice while the array stays fully Meissner-screened
behind them: the flux front stalls at the array perimeter and never reaches a hole.
There is no applied field at which this film holds one or two vortices in
equilibrium; it holds none, or it holds hundreds.

<figure>
  <a href="/projects/tdgl/nb-hole-array-entry.png"><img src="/projects/tdgl/nb-hole-array-entry.png" alt="Order parameter and Bz maps of a 3×3 hole array with the field ramped to 3.6 mT" loading="lazy" /></a>
  <figcaption>Field ramped to 3.6 mT. The vortex lattice fills the buffer and stops at the array perimeter; the interior stays screened.</figcaption>
</figure>

Field-cooling does what the experiment does. ψ grows from near zero with the field
already on, so flux is trapped where it is rather than having to cross 8 µm of
screening metal; the field then drops below the entry threshold and the state
settles. Cooled at 4.0 mT and held at 2.0 mT, after 400 τ<sub>GL</sub>: 3 vortices in
the metal between the holes, 7 flux quanta trapped across the nine, with the rest of
the flux in the buffer lattice. An independent run of the same protocol at another
noise seed gives 2 and 6, with the census flat from t = 293 to t = 400 — so this is a
settled state, not one realisation of the noise.

<figure>
  <a href="/projects/tdgl/nb-hole-array-trapped.png"><img src="/projects/tdgl/nb-hole-array-trapped.png" alt="Field-cooled remanent state of the hole array: order parameter and Bz maps" loading="lazy" /></a>
  <figcaption>Field-cooled at 4 mT, held at 2 mT. The array clears while the holes keep their fluxoid.</figcaption>
</figure>

<figure>
  <img src="/projects/tdgl/nb-hole-array-trapped.gif" alt="Animation of vortices entering and settling in the hole array, each hole labelled with its fluxoid" loading="lazy" />
  <figcaption>Getting there — each hole labelled with the fluxoid it holds.</figcaption>
</figure>

The holes hold about one quantum each rather than the $B A/\Phi_0 \approx 19$ the
applied field would suggest, and the $B_z$ map says why: 8 µm of buffer at
λ = 300 nm leaves the array interior nearly field-free, so there is no local field
there to support more. Per-hole occupancy is set by how well the surround screens,
not by the applied field — which makes the buffer width and κ the levers.

A vortex in the film and a fluxoid in a hole are counted differently, because they
are different things. The first is a core, found from the gauge-invariant phase
winding around a plaquette; the second has no core to find and is read from the
winding on a contour drawn in the metal *around* the hole, which is an exact integer
however little field threads the opening.

## Flux expulsion by an S/I/S ring

A 1 µm hole centred in a 4 µm S/I/S plane with 500 nm layers, at ξ = 100 nm — Nb
near $T_c$, where Ginzburg–Landau applies. The device expels flux completely — no
vortices anywhere, zero fluxoid through the hole — up to 9.2 ± 0.3 mT.

What limits it is not the hole. A 4 µm plane is 20 λ across and screens so well that
only 1.7% of the applied field reaches the hole (0.07 Φ₀ through it at the
threshold), so the ring is nowhere near its fluxoid limit; vortices penetrate the
1.5 µm-wide arms first, and the hole does not admit a fluxoid until 10.9 mT. The
device therefore beats the naive single-loop estimate $\Phi_0/A_\text{hole} = 2.07$ mT
by more than a factor of four.

<figure>
  <a href="/projects/tdgl/sis-micron-ring.png"><img src="/projects/tdgl/sis-micron-ring.png" alt="Four-panel figure: vortex and fluxoid counts against applied field, field at the hole centre, and order-parameter maps below and above threshold" loading="lazy" /></a>
  <figcaption>Vortices enter the plane before the hole gives way. Click for full size.</figcaption>
</figure>

<figure>
  <a href="/projects/tdgl/trilayer-bfield.png"><img src="/projects/tdgl/trilayer-bfield.png" alt="Bz cuts through and across an S/I/S stack, and a Bz map of the field around it" loading="lazy" /></a>
  <figcaption>S/I/S in a perpendicular field — the metal screens, the oxide transmits, and the expelled flux crowds into the vacuum beside the film.</figcaption>
</figure>

## Nucleation and screening currents

<figure>
  <img src="/projects/tdgl/vortex-entry-dynamics.gif" alt="Animation of vortex nucleation: order parameter, phase, and a running vortex count" loading="lazy" />
  <figcaption>Vortices enter from the edges, interact, and settle into a steady population at Bz = 0.5.</figcaption>
</figure>

<figure>
  <a href="/projects/tdgl/supercurrent-hole.png"><img src="/projects/tdgl/supercurrent-hole.png" alt="Supercurrent, normal current and total current streamlines around a square hole" loading="lazy" /></a>
  <figcaption>Supercurrent, normal current and total current around a square hole: J<sub>s</sub> circulates around the hole and vanishes inside it.</figcaption>
</figure>

## Circuits

### A superconducting bridge rectifier

The vortex diode of
[Castellani, Medeiros *et al.* (2024)](https://arxiv.org/abs/2406.12175) is a
wire with a triangular notch on one edge: in a perpendicular field the notch
lets vortices in more easily for one current direction than the other. tdgl3d
rebuilds the diode and then the paper's full-wave rectifier — four diodes and a
normal-metal load — as a single TDGL device.

The diode reproduces the measurement's mechanism: equal critical currents at
zero field (exact, by symmetry) and an efficiency rising linearly with field.
The field scale is within a factor of 4–5 of the chip's, and a static thin-film
London solve of the wire between its contact pads accounts for that factor if the
wire is short against pads of order 100 µm. In the bridge, nothing reaches the
load below twice the reverse diodes' critical current. Between that and twice the
forward one, the load voltage has the same sign for either input polarity: under a
sine drive the output is full-wave. Its average comes within 2% of the DC transfer
curve averaged over the same sine.

<figure>
  <a href="/projects/tdgl/diode-replications.png"><img src="/projects/tdgl/diode-replications.png" alt="Six panels: diode critical currents and efficiency against field, field for 35% efficiency against wire width, the bridge layout, its DC transfer curve and its full-wave AC output" loading="lazy" /></a>
  <figcaption>Top: the notched diode at three widths against the measured device. Bottom: the four-diode bridge, its DC transfer curve, and the rectified output under a sine drive. Click for full size.</figcaption>
</figure>

### Self-heating: a hotspot that switches and latches

Moving vortices and normal current dissipate energy. The dissipation density
$Q = 2|(\partial_t + i\mu)\psi|^2 + 2|E|^2$ drives a heat equation for the reduced
temperature θ, and θ lowers the local $T_c$ margin $\varepsilon = \varepsilon_0 - \theta$. In
a strip with a notch, ramping the current 0 → 5 → 0, phase slips at the notch
heat it past recovery at I ≈ 4.6, and a normal belt spreads across the width,
sustained by its own Joule heat. On the way down it holds until I ≈ 1.9: the
self-heating hysteresis of real nanowires. With heating off, the same ramp shows
only a small phase-slip voltage and never switches.

<figure>
  <img src="/projects/tdgl/heated-hotspot.gif" alt="Animation of a notched strip under a current ramp: order parameter, dissipation and temperature maps above a voltage–current trace" loading="lazy" />
  <figcaption>|ψ|, dissipation Q and temperature θ during the ramp, with the voltage against current below. Heated (red) against isothermal (dashed).</figcaption>
</figure>

### Inductance, impedance and capacitance

A circuit needs its lines' L and C, and three solvers provide them:

- **From TDGL** — inductance per unit length is the stored field plus kinetic
  energy over $I^2$, and a small sinusoidal drive gives the complex impedance
  from the Poynting balance on one cross-section. In a field, the vortices add a
  Campbell-like inductance and dominate the loss at low frequency.
- **Static London extraction** — the port inductance matrix of 3-D
  superconducting wiring, with ports as cuts through the conductor, like a
  junction. It matches Swihart's parallel-plate inductance to 0.39%, and two
  stacked 10 µm Nb rings come out at 19.9 pH each with k = 0.46.
- **Electrostatics** — a 2-D Laplace solve gives the capacitance matrix per
  unit length, matching closed forms for stripline and coplanar waveguide to
  0.1–0.3% and Hammerstad and Jensen's microstrip to 0.25%. With the TDGL
  inductance, that gives $Z_0 = \eta_0\sqrt{L/C}$ and the phase velocity, kinetic
  inductance included.

<figure>
  <a href="/projects/tdgl/ac-response.png"><img src="/projects/tdgl/ac-response.png" alt="Sheet inductance and sheet resistance of a strip against drive frequency, at zero field and with 8 and 20 vortices" loading="lazy" /></a>
  <figcaption>Small-signal response of a strip. Vortices raise the low-frequency inductance up to fivefold and the loss by more than an order of magnitude; at zero field the strip follows the two-fluid model.</figcaption>
</figure>

## Checks against exact solutions

Two limits of the coupled equations have closed-form solutions, and between them they
exercise each equation on its own. Both comparisons have no fitted parameters, and
both run at three grid spacings so the residual can be shown to be discretisation
error rather than disagreement.

In the London limit (|ψ| = 1, so the ψ-equation drops out) a square with the field
pinned on its boundary obeys $\nabla^2 B = B/\lambda^2$, which has an exact Fourier
solution. The solver matches it to rms 4.1e-3 · B₀ at h = 1 ξ, falling to 3.3e-4 at
h = 0.25 ξ — observed order 1.82 in h. On the pinned boundary plaquettes, where the
condition is Dirichlet and the solver should be exact rather than approximate, it
agrees with the applied field to 6e-16.

At a pair-breaking wall (zero field, so the gauge field drops out)
$\psi'' = -\psi + \psi^3$ gives $\tanh((x - x_0)/\sqrt{2})$, with the offset $x_0$
fixed by matching to the insulator's relaxation rather than fitted. The solver
matches it to rms 5.0e-2 at h = 1 ξ, falling to 4.8e-3 at h = 0.25 ξ — observed
order 1.69 in h. The √2 is the physics being checked: the Ginzburg–Landau healing
length is √2 ξ, not ξ.

<figure>
  <a href="/projects/tdgl/analytic-cross-sections.png"><img src="/projects/tdgl/analytic-cross-sections.png" alt="Six-panel comparison of solver cross-sections against closed-form London and pair-breaking-wall solutions, with residuals at three grid spacings" loading="lazy" /></a>
  <figcaption>Cross-sections against closed-form solutions, with the residual at three grid spacings. The bottom row applies the same two models to the micron ring, where neither holds exactly, and says where each stops applying. Click for full size.</figcaption>
</figure>

The 3D path is checked against the same exact solution: a problem with no
z-dependence must be solved identically by the 2D and 3D codes, and it is — the field
varies across z-slices by 2e-16 and differs from the 2D run by 2e-10. Altogether the
verification suites record 294 physics checks — gauge covariance, ∇·B = 0, symmetry,
fluxoid quantisation, the closed-form limits — each with its measured value, the value
physics requires, and the tolerance allowed.

## Scale

The 3×3 hole array above is 1.8 M nodes at ξ = 100 nm, and it is the size that
decides whether a study is an afternoon or a month. Measured on 4 cores, per unit of
Ginzburg–Landau time, with forward Euler at 0.9 of the CFL limit:

| ξ(T) | grid | interior nodes | s per τ<sub>GL</sub> (double / single) | peak RSS (double / single) |
|---|---|---|---|---|
| 150 nm | 240 × 240 × 9 | 457 k | 3.3 / 2.0 | 0.41 / 0.29 GB |
| 100 nm | 360 × 360 × 15 | 1.80 M | 16 / 9.5 | 1.35 / 0.90 GB |
| 70 nm | 514 × 514 × 21 | 5.26 M | 70 / 28 | 3.46 / 2.13 GB |
| 50 nm | 720 × 720 × 30 | 15.0 M | 187 / 106 | 9.58 / 5.73 GB |

All eight were run, not extrapolated. Three knobs matter at that scale: a thread
pool for the right-hand side (bandwidth-bound, so cores help — 2.7× on four),
streaming frames to HDF5 as they are produced so memory holds one frame however long
the run is, and single precision, which cuts both the memory and the bandwidth the
evaluation is limited by.

Where the field evolves, use the IMEX integrator. It takes the stiff
$\kappa^2\nabla\times\nabla\times\mathbf{A}$ term implicitly, solved exactly by sine and cosine
transforms, so the step is set by ψ rather than by κ: 11× faster than forward Euler
at κ = 5 and 170× at κ = 20, agreeing with it to 1e-3 in ψ. Where **A** is frozen,
forward Euler is the same thing. The implicit trapezoidal integrator is not worth
it: its unpreconditioned Newton–GCR solve costs more than the larger step buys.

## Getting started

```bash
git clone https://github.com/omedeiro/nanowire_tdgl.git
cd nanowire_tdgl/packages/tdgl3d
pip install -e ".[dev]"
pytest
```

```python
import tdgl3d

params = tdgl3d.SimulationParameters(
    Nx=20, Ny=20, Nz=4,
    hx=1.0, hy=1.0, hz=1.0,
    kappa=5.0,
)
field = tdgl3d.AppliedField(Bz=1.0, ramp=True, ramp_fraction=0.3)
device = tdgl3d.Device(params, applied_field=field)

solution = tdgl3d.solve(device, t_stop=10.0, dt=0.05, method="euler")

solution.plot_order_parameter(slice_z=2)
```

The hole-array figures are reproduced by
[`packages/tdgl3d/examples/nb_hole_array.py`](https://github.com/omedeiro/nanowire_tdgl/blob/main/packages/tdgl3d/examples/nb_hole_array.py),
whose `--dry-run` prints the grid, the memory per frame and a wall-time estimate
before you commit to a run. Every figure above is produced by a standalone script in
[`docs/figures/`](https://github.com/omedeiro/nanowire_tdgl/tree/main/docs/figures).

## MATLAB predecessor

The Python package is a rewrite of the 3D TDGL MATLAB code written for MIT 6.336
(Spring 2021), verified against it index for index.

<figure>
  <img src="/projects/tdgl/tdgl-evolution.gif" alt="TDGL order parameter and magnetic field time evolution" style="width: 50%; display: block; margin: 0 auto;" loading="lazy" />
  <figcaption>Time evolution of a type-II superconductor under a 0.6 mT applied field in the z-direction, turned off at t=65. Top: 2D color map of the order parameter. Bottom: 2D color map of the z-component of the magnetic field.</figcaption>
</figure>

<figure>
  <img src="/projects/tdgl/trapGif20211201T151612.gif" alt="Rotating view of the |psi|^2 = 0.1 isosurface in a 3D film" loading="lazy" />
  <figcaption>The |ψ|² = 0.1 isosurface in a 3D film, from the same MATLAB code.</figcaption>
</figure>

## Source

[github.com/omedeiro/nanowire_tdgl](https://github.com/omedeiro/nanowire_tdgl) — the
Python solver, the project schema and the job server. The original MATLAB is in
[github.com/omedeiro/simulation6336](https://github.com/omedeiro/simulation6336).

<script src="/projects/tdgl/viewer3d.js" defer></script>
