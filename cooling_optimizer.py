"""Core models and optimization routines for regenerative cooling channel design."""

from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Dict, List, Tuple


@dataclass
class EngineInputs:
    chamber_pressure_mpa: float
    heat_flux_mw_m2: float
    coolant_mass_flow_kg_s: float
    coolant_cp_j_kgk: float
    coolant_density_kg_m3: float
    coolant_viscosity_pa_s: float
    wall_length_m: float


@dataclass
class Geometry:
    channel_count: int
    width_mm: float
    height_mm: float
    rib_thickness_mm: float


def compute_metrics(engine: EngineInputs, geometry: Geometry) -> Dict[str, float]:
    """Estimate thermal and hydraulic performance for a geometry.

    The equations are intentionally lightweight and heuristic so the app can run
    without heavyweight simulation dependencies.
    """

    width_m = geometry.width_mm / 1000.0
    height_m = geometry.height_mm / 1000.0
    area_per_channel = width_m * height_m
    total_flow_area = area_per_channel * geometry.channel_count

    hydraulic_diameter = 2.0 * width_m * height_m / (width_m + height_m)
    velocity = engine.coolant_mass_flow_kg_s / (engine.coolant_density_kg_m3 * total_flow_area)
    reynolds = engine.coolant_density_kg_m3 * velocity * hydraulic_diameter / engine.coolant_viscosity_pa_s

    if reynolds < 2300:
        friction_factor = 64.0 / max(reynolds, 1.0)
    else:
        friction_factor = 0.3164 / (reynolds ** 0.25)

    pressure_drop_pa = (
        friction_factor
        * (engine.wall_length_m / max(hydraulic_diameter, 1e-6))
        * 0.5
        * engine.coolant_density_kg_m3
        * velocity**2
    )

    wetted_perimeter = 2.0 * (width_m + height_m)
    total_surface_area = wetted_perimeter * engine.wall_length_m * geometry.channel_count
    heat_load_w = engine.heat_flux_mw_m2 * 1e6 * total_surface_area
    coolant_delta_t = heat_load_w / max(engine.coolant_mass_flow_kg_s * engine.coolant_cp_j_kgk, 1.0)

    # Lightweight manufacturability proxy (higher is better).
    aspect_ratio = height_m / max(width_m, 1e-6)
    manufacturability = max(0.0, 1.0 - abs(aspect_ratio - 1.5) / 2.5)

    return {
        "velocity_m_s": velocity,
        "reynolds": reynolds,
        "pressure_drop_mpa": pressure_drop_pa / 1e6,
        "coolant_delta_t_k": coolant_delta_t,
        "heat_load_mw": heat_load_w / 1e6,
        "total_flow_area_mm2": total_flow_area * 1e6,
        "manufacturability": manufacturability,
    }


def objective(metrics: Dict[str, float], engine: EngineInputs) -> float:
    """Return a weighted objective value to minimize."""

    pressure_penalty = metrics["pressure_drop_mpa"] / max(engine.chamber_pressure_mpa, 1e-3)
    thermal_penalty = metrics["coolant_delta_t_k"] / 400.0
    manufacturability_bonus = metrics["manufacturability"]

    # Lower score is better.
    return (2.5 * pressure_penalty) + (2.0 * thermal_penalty) - (0.4 * manufacturability_bonus)


def random_search(
    engine: EngineInputs,
    bounds: Dict[str, Tuple[float, float]],
    iterations: int = 1000,
    seed: int = 42,
) -> Tuple[Geometry, Dict[str, float], List[Tuple[Geometry, Dict[str, float], float]]]:
    random.seed(seed)
    history: List[Tuple[Geometry, Dict[str, float], float]] = []

    best_geometry: Geometry | None = None
    best_metrics: Dict[str, float] | None = None
    best_score = float("inf")

    for _ in range(iterations):
        sample = Geometry(
            channel_count=int(random.randint(int(bounds["channel_count"][0]), int(bounds["channel_count"][1]))),
            width_mm=random.uniform(*bounds["width_mm"]),
            height_mm=random.uniform(*bounds["height_mm"]),
            rib_thickness_mm=random.uniform(*bounds["rib_thickness_mm"]),
        )

        metrics = compute_metrics(engine, sample)
        score = objective(metrics, engine)
        history.append((sample, metrics, score))

        if score < best_score:
            best_score = score
            best_geometry = sample
            best_metrics = metrics

    assert best_geometry is not None and best_metrics is not None
    return best_geometry, best_metrics, history


def history_to_text(history: List[Tuple[Geometry, Dict[str, float], float]], top_n: int = 5) -> str:
    ranked = sorted(history, key=lambda item: item[2])[:top_n]
    lines = []
    for index, (geom, metrics, score) in enumerate(ranked, start=1):
        lines.append(
            f"{index}. Score={score:.4f} | N={geom.channel_count}, w={geom.width_mm:.2f} mm, "
            f"h={geom.height_mm:.2f} mm, rib={geom.rib_thickness_mm:.2f} mm, "
            f"dP={metrics['pressure_drop_mpa']:.3f} MPa, dT={metrics['coolant_delta_t_k']:.1f} K"
        )
    return "\n".join(lines)
