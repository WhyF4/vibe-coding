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
    coolant_thermal_conductivity_w_mk: float
    wall_length_m: float


@dataclass
class Geometry:
    channel_count: int
    width_mm: float
    height_mm: float
    rib_thickness_mm: float


def compute_metrics(engine: EngineInputs, geometry: Geometry) -> Dict[str, float]:
    width_m = geometry.width_mm / 1000.0
    height_m = geometry.height_mm / 1000.0
    area_per_channel = width_m * height_m
    total_flow_area = area_per_channel * geometry.channel_count

    hydraulic_diameter = 2.0 * width_m * height_m / (width_m + height_m)
    velocity = engine.coolant_mass_flow_kg_s / (engine.coolant_density_kg_m3 * max(total_flow_area, 1e-9))
    reynolds = engine.coolant_density_kg_m3 * velocity * hydraulic_diameter / max(engine.coolant_viscosity_pa_s, 1e-12)

    if reynolds < 2300:
        friction_factor = 64.0 / max(reynolds, 1.0)
    else:
        friction_factor = 0.3164 / (reynolds**0.25)

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

    aspect_ratio = height_m / max(width_m, 1e-6)
    manufacturability = max(0.0, 1.0 - abs(aspect_ratio - 1.5) / 2.5)

    return {
        "velocity_m_s": velocity,
        "reynolds": reynolds,
        "hydraulic_diameter_m": hydraulic_diameter,
        "pressure_drop_mpa": pressure_drop_pa / 1e6,
        "coolant_delta_t_k": coolant_delta_t,
        "heat_load_mw": heat_load_w / 1e6,
        "total_surface_area_m2": total_surface_area,
        "total_flow_area_mm2": total_flow_area * 1e6,
        "manufacturability": manufacturability,
    }


def estimate_regen_temperatures(
    engine: EngineInputs,
    geometry: Geometry,
    chamber_temp_k: float,
    gamma: float,
    wall_thermal_conductivity_w_mk: float,
    wall_thickness_mm: float,
    coolant_inlet_temp_k: float,
) -> Dict[str, float]:
    metrics = compute_metrics(engine, geometry)
    dt = metrics["hydraulic_diameter_m"]

    # Simplified Bartz-style gas-side HTC proxy.
    pc_pa = engine.chamber_pressure_mpa * 1e6
    cstar = 1600.0
    mu_g = 4.5e-5
    cp_g = 3400.0
    pr_g = max(0.65, min(0.9, 0.72 + 0.06 * (gamma - 1.2)))

    h_g = (
        0.026
        / max(dt, 1e-4) ** 0.2
        * (mu_g**0.2 * cp_g / (pr_g**0.6))
        * (pc_pa / max(cstar, 1.0)) ** 0.8
    )

    re = metrics["reynolds"]
    pr_c = (
        engine.coolant_cp_j_kgk * engine.coolant_viscosity_pa_s / max(engine.coolant_thermal_conductivity_w_mk, 1e-6)
    )
    nu_c = 0.023 * max(re, 1.0) ** 0.8 * max(pr_c, 0.1) ** 0.4
    h_c = nu_c * engine.coolant_thermal_conductivity_w_mk / max(dt, 1e-4)

    r_g = 1.0 / max(h_g, 1e-6)
    r_w = (wall_thickness_mm / 1000.0) / max(wall_thermal_conductivity_w_mk, 1e-6)
    r_c = 1.0 / max(h_c, 1e-6)

    q_flux = (chamber_temp_k - coolant_inlet_temp_k) / max((r_g + r_w + r_c), 1e-9)
    wall_hot = chamber_temp_k - q_flux * r_g
    wall_cold = wall_hot - q_flux * r_w

    total_q = q_flux * metrics["total_surface_area_m2"]
    coolant_outlet = coolant_inlet_temp_k + total_q / max(engine.coolant_mass_flow_kg_s * engine.coolant_cp_j_kgk, 1.0)

    return {
        "h_g_w_m2k": h_g,
        "h_c_w_m2k": h_c,
        "q_flux_mw_m2": q_flux / 1e6,
        "wall_hot_k": wall_hot,
        "wall_cold_k": wall_cold,
        "coolant_outlet_k": coolant_outlet,
        "coolant_rise_k": coolant_outlet - coolant_inlet_temp_k,
    }


def objective(metrics: Dict[str, float], engine: EngineInputs) -> float:
    pressure_penalty = metrics["pressure_drop_mpa"] / max(engine.chamber_pressure_mpa, 1e-3)
    thermal_penalty = metrics["coolant_delta_t_k"] / 400.0
    manufacturability_bonus = metrics["manufacturability"]
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
