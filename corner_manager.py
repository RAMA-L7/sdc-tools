"""
MMC Corner Manager
Data model, presets, validation, and serialization for PVT timing corners.
"""

from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional
import json


@dataclass
class Corner:
    name: str                               # "SSG_0P72V_M40C"
    operating_condition: str = ""            # library condition name (e.g. "SSG_0P72V_M40C")
    voltage: float = 0.72                    # Volts
    temperature: float = -40.0               # Celsius
    process_type: str = "SSG"                # SSG | TT | FFG | SS | FF
    derate_cell_early: float = 1.08
    derate_cell_late: float = 0.92
    derate_net_early: float = 1.0
    derate_net_late: float = 1.0
    uncertainty_scale: float = 1.0           # multiplier on base clock uncertainty


# ── Preset corner collections ──────────────────────────────────────────────────

CLASSIC_3 = [
    Corner(
        name="WORST_SSG_0P72V_M40C",
        operating_condition="SSG_0P72V_M40C",
        voltage=0.72, temperature=-40.0, process_type="SSG",
        derate_cell_early=1.08, derate_cell_late=0.92,
        derate_net_early=1.02, derate_net_late=0.98,
        uncertainty_scale=1.2,
    ),
    Corner(
        name="TYPICAL_TT_0P80V_25C",
        operating_condition="TT_0P80V_25C",
        voltage=0.80, temperature=25.0, process_type="TT",
        derate_cell_early=1.04, derate_cell_late=0.96,
        derate_net_early=1.01, derate_net_late=0.99,
        uncertainty_scale=1.0,
    ),
    Corner(
        name="BEST_FFG_0P88V_125C",
        operating_condition="FFG_0P88V_125C",
        voltage=0.88, temperature=125.0, process_type="FFG",
        derate_cell_early=1.02, derate_cell_late=0.98,
        derate_net_early=1.00, derate_net_late=1.00,
        uncertainty_scale=0.8,
    ),
]

INDUSTRIAL_5 = CLASSIC_3 + [
    Corner(
        name="SSG_0P65V_M40C",
        operating_condition="SSG_0P65V_M40C",
        voltage=0.65, temperature=-40.0, process_type="SSG",
        derate_cell_early=1.10, derate_cell_late=0.90,
        derate_net_early=1.03, derate_net_late=0.97,
        uncertainty_scale=1.3,
    ),
    Corner(
        name="FFG_0P95V_125C",
        operating_condition="FFG_0P95V_125C",
        voltage=0.95, temperature=125.0, process_type="FFG",
        derate_cell_early=1.01, derate_cell_late=0.99,
        derate_net_early=1.00, derate_net_late=1.00,
        uncertainty_scale=0.7,
    ),
]

FULL_8 = INDUSTRIAL_5 + [
    Corner(
        name="SS_0P72V_125C",
        operating_condition="SS_0P72V_125C",
        voltage=0.72, temperature=125.0, process_type="SS",
        derate_cell_early=1.06, derate_cell_late=0.94,
        derate_net_early=1.02, derate_net_late=0.98,
        uncertainty_scale=1.1,
    ),
    Corner(
        name="FF_0P88V_M40C",
        operating_condition="FF_0P88V_M40C",
        voltage=0.88, temperature=-40.0, process_type="FF",
        derate_cell_early=1.03, derate_cell_late=0.97,
        derate_net_early=1.00, derate_net_late=1.00,
        uncertainty_scale=0.9,
    ),
    Corner(
        name="TT_0P80V_0C",
        operating_condition="TT_0P80V_0C",
        voltage=0.80, temperature=0.0, process_type="TT",
        derate_cell_early=1.04, derate_cell_late=0.96,
        derate_net_early=1.01, derate_net_late=0.99,
        uncertainty_scale=1.0,
    ),
]

CORNER_PRESETS: Dict[str, List[Corner]] = {
    "Classic 3-corner (Worst/Typ/Best)": CLASSIC_3,
    "Industrial 5-corner": INDUSTRIAL_5,
    "Full 8-corner signoff": FULL_8,
    "Custom (empty)": [],
}

KNOWN_PROCESS_TYPES = {"SSG", "TT", "FFG", "SS", "FF", "SF", "FS", "SNG", "FNG"}
KNOWN_COMMON_PATTERNS = {
    "WORST", "BEST", "TYP", "TYPICAL",
    "SSG", "TT", "FFG", "SS", "FF",
}


# ── Validation ─────────────────────────────────────────────────────────────────

def validate_corner(c: Corner) -> List[str]:
    """Return a list of validation error messages (empty if valid)."""
    errors = []
    if not c.name or not c.name.strip():
        errors.append("Corner name is required.")
    if not (0.3 <= c.voltage <= 1.5):
        errors.append(f"Voltage {c.voltage}V outside typical range 0.3–1.5V.")
    if not (-55 <= c.temperature <= 175):
        errors.append(f"Temperature {c.temperature}°C outside range -55..175°C.")
    if c.process_type not in KNOWN_PROCESS_TYPES:
        errors.append(f'Process type "{c.process_type}" is not recognized. Expected one of: {", ".join(sorted(KNOWN_PROCESS_TYPES))}')
    if not (0.5 <= c.derate_cell_early <= 1.5):
        errors.append(f"Cell early derate {c.derate_cell_early} outside range 0.5–1.5.")
    if not (0.5 <= c.derate_cell_late <= 1.5):
        errors.append(f"Cell late derate {c.derate_cell_late} outside range 0.5–1.5.")
    if not (0.5 <= c.derate_net_early <= 1.5):
        errors.append(f"Net early derate {c.derate_net_early} outside range 0.5–1.5.")
    if not (0.5 <= c.derate_net_late <= 1.5):
        errors.append(f"Net late derate {c.derate_net_late} outside range 0.5–1.5.")
    if not (0.5 <= c.uncertainty_scale <= 2.0):
        errors.append(f"Uncertainty scale {c.uncertainty_scale} outside range 0.5–2.0.")
    return errors


# ── Serialization ──────────────────────────────────────────────────────────────

def corner_to_dict(c: Corner) -> dict:
    return asdict(c)


def corner_from_dict(d: dict) -> Corner:
    return Corner(**{k: v for k, v in d.items() if k in Corner.__dataclass_fields__})


def corners_to_json(corners: List[Corner]) -> str:
    return json.dumps([corner_to_dict(c) for c in corners], indent=2)


def corners_from_json(text: str) -> List[Corner]:
    data = json.loads(text)
    return [corner_from_dict(d) for d in data]


# ── Coverage Matrix ────────────────────────────────────────────────────────────

def corner_matrix(corners: List[Corner]) -> Dict[str, Dict[str, str]]:
    """Return a summary dict for display: {corner_name: {attribute: value_str}}"""
    matrix = {}
    for c in corners:
        matrix[c.name] = {
            "Process": c.process_type,
            "Voltage (V)": f"{c.voltage:.2f}",
            "Temp (°C)": f"{c.temperature:.0f}",
            "Cell Early": f"{c.derate_cell_early:.3f}",
            "Cell Late": f"{c.derate_cell_late:.3f}",
            "Net Early": f"{c.derate_net_early:.3f}",
            "Net Late": f"{c.derate_net_late:.3f}",
            "Unc Scale": f"{c.uncertainty_scale:.2f}",
            "Op Cond": c.operating_condition or "(none)",
        }
    return matrix
