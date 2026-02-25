# Rocket Engine Pre-Design Applet

A lightweight desktop applet for early-stage rocket engine sizing and nozzle geometry visualization.

## Features

- Select common **fuel/oxidizer pairs** using dropdowns.
- Input **thrust**, **chamber pressure**, and **O/F ratio**.
- Run a lightweight conceptual **thermochemistry estimate** for `c*` and `Isp,vac`.
- Size basic engine parameters (throat/exit radii, mass flow, nozzle length).
- Choose **conical** or **parabolic** nozzle and configure key nozzle parameters.
- View a built-in **2D nozzle contour** plot in the GUI.
- Switch common **units** with dropdowns:
  - thrust: `N`, `kN`, `lbf`
  - pressure: `MPa`, `bar`, `psi`
  - length output: `mm`, `m`, `in`

> This app is intended for conceptual studies and first-pass sizing, not high-fidelity CEA/CFD/CHT certification work.

## Quick start

```bash
python app.py
```

No third-party dependencies are required (`tkinter` is part of Python stdlib).

## Included propellant pairs

- RP-1 / LOX
- Liquid Methane / LOX
- Liquid Hydrogen / LOX
- Ethanol / LOX
- IPA / LOX
- Jet-A / LOX

## Files

- `app.py`: GUI, input handling, and nozzle contour drawing.
- `engine_design.py`: conceptual thermochemistry, sizing model, and unit conversions.
- `cooling_optimizer.py`: existing regenerative cooling channel optimizer backend.

## Model notes

The thermochemistry and nozzle sizing are simplified trend models intended for speed and transparency. Use this tool for fast trade studies, then refine with higher-fidelity tools for detailed design.
