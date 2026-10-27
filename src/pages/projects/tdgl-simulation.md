---
layout: ../../layouts/Md.astro
title: TDGL Simulation
description: tdgl3d, a fully 3-D superconducting circuit simulator built on the time-dependent Ginzburg–Landau equations, and TDGL Lab, its web app with a live simulator, the physics gallery and the checks against the literature.
---

tdgl3d is a fully three-dimensional simulator for superconducting devices and
circuits, built on the time-dependent Ginzburg–Landau (TDGL) equations. It
resolves what circuit models leave out: where vortices enter, how they move under
a bias current, where they dissipate, and how much the film heats. Stacked
metal–insulator–metal layers, holes, notches and the vacuum around the conductor
are all on one 3-D grid, so the third dimension is part of the physics rather than
an extrusion of a 2-D film.

$$
\frac{\partial \psi}{\partial t} = (\nabla - i\mathbf{A})^2 \psi + (1 - |\psi|^2)\,\psi
$$

$$
\frac{\partial \mathbf{A}}{\partial t} = \kappa^2 \nabla \times (\nabla \times \mathbf{A}) - \mathrm{Im}\!\left[\psi^* (\nabla - i\mathbf{A})\psi\right]
$$

**[Open TDGL Lab →](https://tdgl.owenmedeiros.com)**

<figure>
  <a href="https://tdgl.owenmedeiros.com/#sim"><img src="/projects/tdgl/live-nbn-3d.png" alt="3-D render of an NbN block between two gold contacts on SiO2 and silicon, its top face coloured by the order parameter with dark spots at the vortices" loading="lazy" /></a>
  <figcaption>The live simulator in TDGL Lab: a 3-D NbN block on SiO₂ over silicon at 4.2 K, with bias current, field, heat and photon absorption, solved on your GPU.</figcaption>
</figure>

## TDGL Lab

TDGL Lab is the project's web app. It has five parts:

- **Tutorial** — ten short chapters from the equations to whole devices: screening,
  vortex entry, trapped flux, phase slips and flux flow, hotspots, photon detection,
  diodes and hTrons, and what changes in 3-D. Each one links its examples and a
  preset to run.
- **Simulator** — the live 3-D NbN block, with presets for a photon detection, an
  I–V sweep that switches and latches, flux flow, phase windings and a tilted field.
  It checks its GPU against a double-precision reference that matches tdgl3d to
  round-off before it runs.
- **Examples** — every section of the physics gallery and the replications of
  published results, each in the same format: figures, animations or a 3-D scene
  you can rotate, the parameters it ran at, and the test that checks it.
- **Verification** — the numbers from the literature the model should reproduce,
  with the value tdgl3d gets and what is still open.
- **Reference** — units, scale, and how to install and run the Python package.

## A few results

- A photon in a 52 ξ NbN strip is detected at 0.921 of the depairing current,
  against 0.90 in [Zotova and Vodolazov (2012)](https://arxiv.org/abs/1112.3790).
- The vortex diode and full-wave bridge rectifier of
  [Castellani, Medeiros *et al.* (2024)](https://arxiv.org/abs/2406.12175) run as one
  TDGL device. The mechanism matches; the field scale is within a factor of 4–5 of
  the chip's.
- In a field tilted 45° from a 3 ξ film's normal, the mean field inside leans 47°
  but the vortex cores lean only 29°, which a 2-D film can't show.

## Source

[github.com/omedeiro/nanowire_tdgl](https://github.com/omedeiro/nanowire_tdgl) holds the
Python solver, the project schema, the job server and TDGL Lab itself. The original
MATLAB code, written for MIT 6.336 (Spring 2021), is in
[github.com/omedeiro/simulation6336](https://github.com/omedeiro/simulation6336).
