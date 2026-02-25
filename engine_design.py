"""Lightweight thermochemistry and engine pre-design helpers for rocket nozzles."""

from __future__ import annotations

from dataclasses import dataclass
from math import log10, pi, sqrt, tan, radians
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


@dataclass(frozen=True)
class NozzleConfig:
    nozzle_type: str
    expansion_ratio: float
    conical_half_angle_deg: float
    bell_length_percent: float


@dataclass(frozen=True)
class EngineSizingResult:
    cstar_m_s: float
    cf: float
    isp_vac_s: float
    mass_flow_kg_s: float
    throat_area_m2: float
    throat_radius_m: float
    exit_area_m2: float
    exit_radius_m: float
    nozzle_length_m: float


PROPELLANT_DB: Dict[Tuple[str, str], PropellantPair] = {
    ("RP-1", "LOX"): PropellantPair("RP-1", "LOX", of_opt=2.6, cstar_ref_m_s=1780.0, isp_vac_ref_s=335.0),
    ("Liquid Methane", "LOX"): PropellantPair(
        "Liquid Methane", "LOX", of_opt=3.4, cstar_ref_m_s=1860.0, isp_vac_ref_s=365.0
    ),
    ("Liquid Hydrogen", "LOX"): PropellantPair(
        "Liquid Hydrogen", "LOX", of_opt=5.6, cstar_ref_m_s=2320.0, isp_vac_ref_s=452.0
    ),
    ("Ethanol", "LOX"): PropellantPair("Ethanol", "LOX", of_opt=1.4, cstar_ref_m_s=1650.0, isp_vac_ref_s=310.0),
    ("IPA", "LOX"): PropellantPair("IPA", "LOX", of_opt=1.6, cstar_ref_m_s=1680.0, isp_vac_ref_s=318.0),
    ("Jet-A", "LOX"): PropellantPair("Jet-A", "LOX", of_opt=2.7, cstar_ref_m_s=1750.0, isp_vac_ref_s=330.0),
}


def list_fuels() -> List[str]:
    return sorted({fuel for fuel, _ in PROPELLANT_DB})


def list_oxidizers() -> List[str]:
    return sorted({ox for _, ox in PROPELLANT_DB})


def get_propellant_pair(fuel: str, oxidizer: str) -> PropellantPair:
    key = (fuel, oxidizer)
    if key not in PROPELLANT_DB:
        raise ValueError(f"Unsupported propellant pair: {fuel} / {oxidizer}")
    return PROPELLANT_DB[key]


def run_thermochemistry(fuel: str, oxidizer: str, of_ratio: float, chamber_pressure_mpa: float) -> Dict[str, float]:
    """Return approximate c* and Isp trends from reference values.

    This is intentionally a fast conceptual model rather than full-equilibrium CEA.
    """

    pair = get_propellant_pair(fuel, oxidizer)

    of_penalty = max(0.75, 1.0 - 0.06 * abs(of_ratio - pair.of_opt))
    pressure_factor = 1.0 + 0.018 * log10(max(chamber_pressure_mpa, 0.2) / 10.0)

    cstar_m_s = pair.cstar_ref_m_s * of_penalty
    isp_vac_s = pair.isp_vac_ref_s * of_penalty * pressure_factor

    return {
        "cstar_m_s": cstar_m_s,
        "isp_vac_s": isp_vac_s,
        "of_opt": pair.of_opt,
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

    cf_base = thermo["isp_vac_s"] * G0 / max(thermo["cstar_m_s"], 1.0)
    cf = cf_base * (1.0 + 0.015 * ((nozzle.expansion_ratio - 40.0) / 40.0))

    pc_pa = chamber_pressure_mpa * PA_PER_MPA
    throat_area = thrust_n / max(cf * pc_pa, 1.0)
    throat_radius = sqrt(throat_area / pi)
    exit_area = throat_area * nozzle.expansion_ratio
    exit_radius = sqrt(exit_area / pi)

    conical_len = (exit_radius - throat_radius) / tan(radians(max(nozzle.conical_half_angle_deg, 1.0)))
    if nozzle.nozzle_type == "Conical":
        nozzle_length = conical_len
    else:
        nozzle_length = conical_len * (nozzle.bell_length_percent / 100.0)

    mass_flow = pc_pa * throat_area / max(thermo["cstar_m_s"], 1.0)

    return EngineSizingResult(
        cstar_m_s=thermo["cstar_m_s"],
        cf=cf,
        isp_vac_s=thermo["isp_vac_s"],
        mass_flow_kg_s=mass_flow,
        throat_area_m2=throat_area,
        throat_radius_m=throat_radius,
        exit_area_m2=exit_area,
        exit_radius_m=exit_radius,
        nozzle_length_m=nozzle_length,
    )


def generate_nozzle_contour(result: EngineSizingResult, nozzle: NozzleConfig) -> List[Tuple[float, float]]:
    """Generate upper-wall (x, r) points from chamber end to exit in meters."""

    rt = result.throat_radius_m
    re = result.exit_radius_m
    conv_len = 1.2 * rt
    chamber_r = 1.6 * rt

    points: List[Tuple[float, float]] = [(-conv_len, chamber_r), (0.0, rt)]

    if nozzle.nozzle_type == "Conical":
        points.append((result.nozzle_length_m, re))
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
        x = L * t
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


def meters_to_unit(value_m: float, unit: str) -> float:
    if unit == "m":
        return value_m
    if unit == "mm":
        return value_m * 1000.0
    if unit == "in":
        return value_m * 39.37007874
    raise ValueError(f"Unsupported length unit: {unit}")
