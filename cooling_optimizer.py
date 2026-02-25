"""Core models and optimization routines for regenerative cooling channel design."""

from __future__ import annotations

from dataclasses import dataclass
from math import pi
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


@dataclass
class AxialStationResult:
    x_m: float
    area_ratio: float
    mach: float
    hg_w_m2k: float
    hc_w_m2k: float
    q_mw_m2: float
    wall_hot_k: float
    wall_cold_k: float
    coolant_bulk_k: float
    pressure_drop_mpa: float


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
        "friction_factor": friction_factor,
        "pressure_drop_mpa": pressure_drop_pa / 1e6,
        "coolant_delta_t_k": coolant_delta_t,
        "heat_load_mw": heat_load_w / 1e6,
        "total_surface_area_m2": total_surface_area,
        "total_flow_area_mm2": total_flow_area * 1e6,
        "manufacturability": manufacturability,
    }


def _solve_mach_from_area_ratio(area_ratio: float, gamma: float, supersonic: bool) -> float:
    target = max(area_ratio, 1.0)
    lo, hi = (1.0001, 8.0) if supersonic else (0.01, 0.999)

    def f(m: float) -> float:
        term = (2.0 / (gamma + 1.0)) * (1.0 + 0.5 * (gamma - 1.0) * m**2)
        area = (1.0 / m) * term ** ((gamma + 1.0) / (2.0 * (gamma - 1.0)))
        return area

    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if supersonic:
            if f(mid) < target:
                lo = mid
            else:
                hi = mid
        else:
            if f(mid) > target:
                lo = mid
            else:
                hi = mid
    return 0.5 * (lo + hi)


def bartz_htc(
    gas_viscosity_pa_s: float,
    gas_cp_j_kgk: float,
    gas_pr: float,
    chamber_pressure_pa: float,
    cstar_m_s: float,
    throat_diameter_m: float,
    throat_curve_radius_m: float,
    at_over_a: float,
    gamma: float,
    mach: float,
    t0_k: float,
    wall_hot_guess_k: float,
) -> float:
    """Bartz relation per user-provided form."""

    sigma = (
        1.0
        / (
            (0.5 * (wall_hot_guess_k / max(t0_k, 1e-6)) * (1.0 + (gamma - 1.0) * 0.5 * mach**2) + 0.5) ** 0.68
            * (1.0 + (gamma - 1.0) * 0.5 * mach**2) ** 0.12
        )
    )

    hg = (
        (0.026 / max(throat_diameter_m, 1e-6) ** 0.2)
        * ((gas_viscosity_pa_s**0.2 * gas_cp_j_kgk) / max(gas_pr, 1e-6) ** 0.6)
        * (chamber_pressure_pa / max(cstar_m_s, 1e-6)) ** 0.8
        * (throat_diameter_m / max(throat_curve_radius_m, 1e-6)) ** 0.1
        * max(at_over_a, 1e-6) ** 0.9
    ) / max(sigma, 1e-6)
    return hg


def solve_regen_axial(
    engine: EngineInputs,
    geometry: Geometry,
    x_stations_m: List[float],
    radius_stations_m: List[float],
    chamber_temp_k: float,
    gamma: float,
    wall_thermal_conductivity_w_mk: float,
    wall_thickness_mm: float,
    coolant_inlet_temp_k: float,
    throat_radius_m: float,
    throat_curve_radius_m: float,
    cstar_m_s: float,
    gas_viscosity_pa_s: float = 4.5e-5,
    gas_cp_j_kgk: float = 3400.0,
    gas_pr: float = 0.72,
) -> List[AxialStationResult]:
    metrics = compute_metrics(engine, geometry)
    dh = metrics["hydraulic_diameter_m"]
    re = metrics["reynolds"]
    pr_c = engine.coolant_cp_j_kgk * engine.coolant_viscosity_pa_s / max(engine.coolant_thermal_conductivity_w_mk, 1e-6)
    nu_c = 0.023 * max(re, 1.0) ** 0.8 * max(pr_c, 0.1) ** 0.4
    hc = nu_c * engine.coolant_thermal_conductivity_w_mk / max(dh, 1e-6)

    wall_thickness_m = wall_thickness_mm / 1000.0
    wetted_perimeter = 2.0 * ((geometry.width_mm + geometry.height_mm) / 1000.0)

    results: List[AxialStationResult] = []
    coolant_temp = coolant_inlet_temp_k
    cumulative_dp_pa = 0.0

    chamber_pressure_pa = engine.chamber_pressure_mpa * 1e6
    throat_area = pi * throat_radius_m**2
    total_len = max(x_stations_m[-1] - x_stations_m[0], 1e-6)

    for i in range(len(x_stations_m)):
        x = x_stations_m[i]
        r = max(radius_stations_m[i], throat_radius_m)
        area = pi * r**2
        area_ratio = area / max(throat_area, 1e-9)

        mach = _solve_mach_from_area_ratio(area_ratio, gamma, supersonic=x >= x_stations_m[len(x_stations_m) // 2])
        at_over_a = 1.0 / max(area_ratio, 1e-9)

        wall_hot = chamber_temp_k * 0.75
        for _ in range(12):
            hg = bartz_htc(
                gas_viscosity_pa_s=gas_viscosity_pa_s,
                gas_cp_j_kgk=gas_cp_j_kgk,
                gas_pr=gas_pr,
                chamber_pressure_pa=chamber_pressure_pa,
                cstar_m_s=cstar_m_s,
                throat_diameter_m=2.0 * throat_radius_m,
                throat_curve_radius_m=throat_curve_radius_m,
                at_over_a=at_over_a,
                gamma=gamma,
                mach=mach,
                t0_k=chamber_temp_k,
                wall_hot_guess_k=wall_hot,
            )

            rg = 1.0 / max(hg, 1e-8)
            rw = wall_thickness_m / max(wall_thermal_conductivity_w_mk, 1e-8)
            rc = 1.0 / max(hc, 1e-8)
            q = (chamber_temp_k - coolant_temp) / max(rg + rw + rc, 1e-9)
            new_wall_hot = chamber_temp_k - q * rg
            if abs(new_wall_hot - wall_hot) < 1e-3:
                wall_hot = new_wall_hot
                break
            wall_hot = 0.6 * wall_hot + 0.4 * new_wall_hot

        wall_cold = wall_hot - q * rw

        if i < len(x_stations_m) - 1:
            dx = max(x_stations_m[i + 1] - x, 0.0)
        else:
            dx = max(x - x_stations_m[i - 1], 0.0) if i > 0 else total_len

        seg_area = wetted_perimeter * dx * geometry.channel_count
        coolant_temp += q * seg_area / max(engine.coolant_mass_flow_kg_s * engine.coolant_cp_j_kgk, 1.0)

        dp_seg = (
            metrics["friction_factor"]
            * (dx / max(dh, 1e-6))
            * 0.5
            * engine.coolant_density_kg_m3
            * metrics["velocity_m_s"] ** 2
        )
        cumulative_dp_pa += dp_seg

        results.append(
            AxialStationResult(
                x_m=x,
                area_ratio=area_ratio,
                mach=mach,
                hg_w_m2k=hg,
                hc_w_m2k=hc,
                q_mw_m2=q / 1e6,
                wall_hot_k=wall_hot,
                wall_cold_k=wall_cold,
                coolant_bulk_k=coolant_temp,
                pressure_drop_mpa=cumulative_dp_pa / 1e6,
            )
        )

    return results


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
