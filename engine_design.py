"""Lightweight thermochemistry and engine pre-design helpers for rocket nozzles."""

from __future__ import annotations

from dataclasses import dataclass
from math import log10, pi, radians, sqrt, tan
from typing import Dict, List, Tuple

G0 = 9.80665
PA_PER_MPA = 1_000_000.0


@dataclass(frozen=True)
class PropellantPair:
    fuel: str
    oxidizer: str
    of_opt: float
    cstar_ref_m_s: float
    isp_vac_ref_s: float
    gamma: float
    flame_temp_k: float


@dataclass(frozen=True)
class NozzleConfig:
    nozzle_type: str
    exit_pressure_mpa: float
    converging_half_angle_deg: float
    conical_half_angle_deg: float
    bell_length_percent: float
    lstar_m: float
    contraction_ratio: float


@dataclass(frozen=True)
class EngineSizingResult:
    cstar_m_s: float
    cf: float
    isp_vac_s: float
    gamma: float
    flame_temp_k: float
    mass_flow_kg_s: float
    fuel_flow_kg_s: float
    oxidizer_flow_kg_s: float
    throat_area_m2: float
    throat_radius_m: float
    exit_area_m2: float
    exit_radius_m: float
    expansion_ratio: float
    chamber_radius_m: float
    chamber_length_m: float
    converging_length_m: float
    nozzle_length_m: float


PROPELLANT_DB: Dict[Tuple[str, str], PropellantPair] = {
    ("RP-1", "LOX"): PropellantPair("RP-1", "LOX", 2.6, 1780.0, 335.0, 1.22, 3670.0),
    ("Liquid Methane", "LOX"): PropellantPair("Liquid Methane", "LOX", 3.4, 1860.0, 365.0, 1.21, 3550.0),
    ("Liquid Hydrogen", "LOX"): PropellantPair("Liquid Hydrogen", "LOX", 5.6, 2320.0, 452.0, 1.20, 3600.0),
    ("Ethanol", "LOX"): PropellantPair("Ethanol", "LOX", 1.4, 1650.0, 310.0, 1.24, 3400.0),
    ("IPA", "LOX"): PropellantPair("IPA", "LOX", 1.6, 1680.0, 318.0, 1.24, 3450.0),
    ("Jet-A", "LOX"): PropellantPair("Jet-A", "LOX", 2.7, 1750.0, 330.0, 1.22, 3600.0),
    ("Ethanol", "N2O"): PropellantPair("Ethanol", "N2O", 6.5, 1540.0, 292.0, 1.25, 3200.0),
    ("IPA", "N2O"): PropellantPair("IPA", "N2O", 7.0, 1560.0, 296.0, 1.25, 3250.0),
    ("RP-1", "N2O"): PropellantPair("RP-1", "N2O", 7.8, 1600.0, 302.0, 1.24, 3300.0),
    ("Liquid Methane", "N2O"): PropellantPair("Liquid Methane", "N2O", 5.8, 1660.0, 312.0, 1.23, 3350.0),
}


def list_fuels() -> List[str]:
    return sorted({fuel for fuel, _ in PROPELLANT_DB})


def list_oxidizers() -> List[str]:
    return sorted({ox for _, ox in PROPELLANT_DB})


def list_pairs_for_fuel(fuel: str) -> List[str]:
    return sorted({ox for (db_fuel, ox) in PROPELLANT_DB if db_fuel == fuel})


def get_propellant_pair(fuel: str, oxidizer: str) -> PropellantPair:
    key = (fuel, oxidizer)
    if key not in PROPELLANT_DB:
        raise ValueError(f"Unsupported propellant pair: {fuel} / {oxidizer}")
    return PROPELLANT_DB[key]


def solve_exit_mach_from_pressure_ratio(pe_over_pc: float, gamma: float) -> float:
    target = min(max(pe_over_pc, 1e-6), 0.95)
    lo, hi = 1.0001, 10.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        ratio = (1.0 + 0.5 * (gamma - 1.0) * mid**2) ** (-gamma / (gamma - 1.0))
        if ratio > target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def expansion_ratio_from_mach(mach: float, gamma: float) -> float:
    term = (2.0 / (gamma + 1.0)) * (1.0 + 0.5 * (gamma - 1.0) * mach**2)
    return (1.0 / mach) * (term ** ((gamma + 1.0) / (2.0 * (gamma - 1.0))))


def run_thermochemistry(fuel: str, oxidizer: str, of_ratio: float, chamber_pressure_mpa: float) -> Dict[str, float]:
    pair = get_propellant_pair(fuel, oxidizer)

    of_penalty = max(0.74, 1.0 - 0.055 * abs(of_ratio - pair.of_opt))
    pressure_factor = 1.0 + 0.018 * log10(max(chamber_pressure_mpa, 0.2) / 10.0)

    cstar_m_s = pair.cstar_ref_m_s * of_penalty
    isp_vac_s = pair.isp_vac_ref_s * of_penalty * pressure_factor

    return {
        "cstar_m_s": cstar_m_s,
        "isp_vac_s": isp_vac_s,
        "of_opt": pair.of_opt,
        "gamma": pair.gamma,
        "flame_temp_k": pair.flame_temp_k,
    }


def size_engine(
    thrust_n: float,
    chamber_pressure_mpa: float,
    of_ratio: float,
    fuel: str,
    oxidizer: str,
    nozzle: NozzleConfig,
) -> EngineSizingResult:
    thermo = run_thermochemistry(fuel, oxidizer, of_ratio, chamber_pressure_mpa)

    pc_pa = chamber_pressure_mpa * PA_PER_MPA
    pe_pa = nozzle.exit_pressure_mpa * PA_PER_MPA
    pe_over_pc = max(min(pe_pa / max(pc_pa, 1.0), 0.95), 1e-6)

    gamma = thermo["gamma"]
    me = solve_exit_mach_from_pressure_ratio(pe_over_pc, gamma)
    expansion_ratio = expansion_ratio_from_mach(me, gamma)

    cf_ideal = sqrt(
        (2 * gamma**2 / (gamma - 1.0))
        * (2.0 / (gamma + 1.0)) ** ((gamma + 1.0) / (gamma - 1.0))
        * (1.0 - pe_over_pc ** ((gamma - 1.0) / gamma))
    )
    cf = cf_ideal

    throat_area = thrust_n / max(cf * pc_pa, 1.0)
    throat_radius = sqrt(throat_area / pi)
    exit_area = throat_area * expansion_ratio
    exit_radius = sqrt(exit_area / pi)

    chamber_area = throat_area * nozzle.contraction_ratio
    chamber_radius = sqrt(chamber_area / pi)
    chamber_length = (nozzle.lstar_m * throat_area) / max(chamber_area, 1e-9)

    converging_length = (chamber_radius - throat_radius) / tan(radians(max(nozzle.converging_half_angle_deg, 1.0)))
    conical_len = (exit_radius - throat_radius) / tan(radians(max(nozzle.conical_half_angle_deg, 1.0)))
    if nozzle.nozzle_type == "Conical":
        nozzle_length = conical_len
    else:
        nozzle_length = conical_len * (nozzle.bell_length_percent / 100.0)

    mass_flow = pc_pa * throat_area / max(thermo["cstar_m_s"], 1.0)
    fuel_flow = mass_flow / (1.0 + of_ratio)
    oxidizer_flow = mass_flow - fuel_flow

    return EngineSizingResult(
        cstar_m_s=thermo["cstar_m_s"],
        cf=cf,
        isp_vac_s=thermo["isp_vac_s"],
        gamma=gamma,
        flame_temp_k=thermo["flame_temp_k"],
        mass_flow_kg_s=mass_flow,
        fuel_flow_kg_s=fuel_flow,
        oxidizer_flow_kg_s=oxidizer_flow,
        throat_area_m2=throat_area,
        throat_radius_m=throat_radius,
        exit_area_m2=exit_area,
        exit_radius_m=exit_radius,
        expansion_ratio=expansion_ratio,
        chamber_radius_m=chamber_radius,
        chamber_length_m=chamber_length,
        converging_length_m=converging_length,
        nozzle_length_m=nozzle_length,
    )


def generate_engine_contour(result: EngineSizingResult, nozzle: NozzleConfig) -> List[Tuple[float, float]]:
    """Generate upper-wall (x, r) points from chamber start to nozzle exit in meters."""

    rc = result.chamber_radius_m
    rt = result.throat_radius_m
    re = result.exit_radius_m

    x0 = 0.0
    x1 = result.chamber_length_m
    x2 = x1 + result.converging_length_m

    points: List[Tuple[float, float]] = [(x0, rc), (x1, rc), (x2, rt)]

    if nozzle.nozzle_type == "Conical":
        points.append((x2 + result.nozzle_length_m, re))
        return points

    L = result.nozzle_length_m
    theta_n = radians(30.0)
    theta_e = radians(8.0)
    m0 = tan(theta_n)
    m1 = tan(theta_e)
    segments = 40

    for i in range(1, segments + 1):
        t = i / segments
        h00 = (2 * t**3) - (3 * t**2) + 1
        h10 = t**3 - (2 * t**2) + t
        h01 = (-2 * t**3) + (3 * t**2)
        h11 = t**3 - t**2
        x = x2 + L * t
        y = h00 * rt + h10 * L * m0 + h01 * re + h11 * L * m1
        points.append((x, y))

    return points


def thrust_to_newton(value: float, unit: str) -> float:
    if unit == "N":
        return value
    if unit == "kN":
        return value * 1000.0
    if unit == "lbf":
        return value * 4.4482216153
    raise ValueError(f"Unsupported thrust unit: {unit}")


def pressure_to_mpa(value: float, unit: str) -> float:
    if unit == "MPa":
        return value
    if unit == "bar":
        return value * 0.1
    if unit == "psi":
        return value * 0.00689475729
    raise ValueError(f"Unsupported pressure unit: {unit}")


def mpa_to_pressure(value_mpa: float, unit: str) -> float:
    if unit == "MPa":
        return value_mpa
    if unit == "bar":
        return value_mpa * 10.0
    if unit == "psi":
        return value_mpa * 145.03773773
    raise ValueError(f"Unsupported pressure unit: {unit}")


def meters_to_unit(value_m: float, unit: str) -> float:
    if unit == "m":
        return value_m
    if unit == "mm":
        return value_m * 1000.0
    if unit == "in":
        return value_m * 39.37007874
    raise ValueError(f"Unsupported length unit: {unit}")
