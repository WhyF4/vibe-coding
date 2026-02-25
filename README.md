# Regenerative Cooling Channel Optimizer Applet

A lightweight desktop applet for **early-stage regenerative cooling channel design** in rocket engines.

It provides:
- A user-friendly GUI to enter engine/coolant parameters.
- Tunable geometry bounds (channel count, width, height, rib thickness).
- A fast random-search optimizer that balances pressure drop, coolant temperature rise, and manufacturability.
- Ranked top candidate geometries.

> This tool is for conceptual trade studies, not high-fidelity CFD/CHT certification.

## Quick start

```bash
python app.py
```

No third-party dependencies are required (uses built-in `tkinter`).

## Model assumptions

The backend uses simple, transparent correlations:
- Hydraulic diameter and flow velocity from channel dimensions.
- Laminar/turbulent friction estimate for pressure drop.
- Total heat load estimate from heat flux × wetted area.
- Coolant temperature rise from energy balance.
- A heuristic manufacturability score based on aspect ratio preference.

The optimizer minimizes a weighted score:

```text
score = 2.5 * pressure_penalty + 2.0 * thermal_penalty - 0.4 * manufacturability_bonus
```

You can adapt these weights in `cooling_optimizer.py`.

## Suggested next upgrades

- Add constraints for max wall temperature and stress limits.
- Add gradient-based/local refinement after random search.
- Export results to CSV/JSON.
- Support axial zoning (different channel geometry by station).
- Integrate real propellant property tables.
