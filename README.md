# Rocket Engine Design + Regen Cooling Applet

A desktop applet for conceptual rocket engine pre-design and regenerative cooling optimization.

## What’s included

### Tab 1: Engine Design
- Fuel/oxidizer dropdowns with common combinations, including **N2O** oxidizer options.
- Inputs for thrust, chamber pressure, exit pressure, and O/F ratio.
- Suggested optimal O/F displayed for the selected propellant pair.
- Chamber/nozzle configuration:
  - converging half-angle,
  - diverging half-angle,
  - conical/parabolic nozzle mode,
  - bell-length percent (for parabolic),
  - L* and contraction ratio.
- Computes engine sizing and thermochemistry trend outputs:
  - c*, Isp(vac), Cf,
  - mass flow split,
  - chamber geometry,
  - computed optimal expansion ratio from Pc/Pe.
- Renders a **2D chamber + nozzle contour** with axes and unit labels.

### Tab 2: Regen Cooling
- Keeps the regenerative cooling channel optimization workflow.
- Supports coolant presets and editable fluid properties.
- Imports key values from Engine Design tab (fuel flow proxy, wall length, gas temp, gamma, heat flux guess).
- Optimizes channel geometry with random search.
- Uses a simplified **Bartz-style** gas-side HTC estimate plus coolant-side convection and wall conduction to estimate:
  - heat flux,
  - hot/cold wall temperatures,
  - coolant outlet temperature and rise.

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
- `engine_design.py`: thermochemistry trends, Pc/Pe-derived expansion ratio, chamber/nozzle sizing, contour generation, unit conversions.
- `cooling_optimizer.py`: channel optimization and Bartz-based temperature estimation.

> This tool is intended for preliminary trade studies, not final high-fidelity performance/certification analysis.
