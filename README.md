# Rocket Engine Design + Regen Cooling Applet

A desktop applet for conceptual rocket engine pre-design and regenerative cooling optimization.

## What’s included

### Tab 1: Engine Design
- Fuel/oxidizer dropdowns with common combinations, including **N2O** options.
- Inputs for thrust, chamber pressure, exit pressure, and O/F ratio.
- Suggested optimal O/F displayed for each propellant pair.
- Chamber/nozzle controls:
  - converging half-angle,
  - diverging half-angle,
  - conical/parabolic mode,
  - bell-length percent,
  - L* and contraction ratio.
- Computes engine sizing including:
  - c*, Isp(vac), Cf,
  - mass flow split,
  - chamber geometry,
  - **computed expansion ratio from Pc/Pe**.
- Renders a **2D chamber + nozzle contour** with axis labels and units.

### Tab 2: Regen Cooling
- Keeps channel geometry optimization (random search).
- Uses a **Bartz-based** gas-side heat transfer coefficient relation using the standard sigma correction form.
- Solves regenerative heat transfer over a user-selected number of **axial stations**.
- Produces:
  1. plot of axial values (`T_wall_hot`, `T_wall_cold`, `T_coolant`, `q"`),
  2. table of station outputs (`x`, `A/At`, `Mach`, `h_g`, `h_c`, `q"`, temperatures, cumulative coolant ΔP).
- Includes `Load from engine tab` to feed engine-design outputs into regen setup.

## Units
- Thrust: `N`, `kN`, `lbf`
- Pressure: `MPa`, `bar`, `psi`
- Length display: `mm`, `m`, `in`

## Quick start

```bash
python app.py
```

No third-party dependencies are required (`tkinter` only).

## Main files
- `app.py`: GUI with Engine Design + Regen Cooling tabs.
- `engine_design.py`: thermochemistry trends, Pc/Pe-derived expansion ratio, chamber/nozzle sizing, contour generation.
- `cooling_optimizer.py`: cooling geometry optimization + Bartz-based axial thermal solver.

> This tool is intended for preliminary trade studies, not final high-fidelity performance/certification analysis.
