"""
SDC Constraint Coverage Analyzer
Parses SDC files and measures which constraint categories are covered vs.
missing — the "gap analysis" that Ausdia TimeVision provides.

6 categories, each with sub-items:
  1. Clocks         — create_clock, latency, transition, uncertainty, propagated
  2. I/O            — input_delay, output_delay, driving_cell, load
  3. Exceptions     — false_path, multicycle, max_delay, min_delay
  4. Design Rules   — max_fanout, max_transition, max_capacitance, max_area
  5. AOCV / Derate  — timing_derate, operating_conditions
  6. Power / DFT    — max_dynamic_power, max_leakage_power, case_analysis, dont_use

Every sub-item is "present" or "missing" → coverage score = present / total.
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class CoverageItem:
    """One constraint sub-item within a category."""
    name: str                # human label, e.g. "create_clock"
    cmd: str                 # SDC command pattern, e.g. "create_clock"
    present: bool            # found in the SDC?
    detail: str = ""         # extra info (count, first value, etc.)
    is_critical: bool = True # True = high-impact if missing


@dataclass
class CoverageCategory:
    """A group of related constraint items."""
    name: str                 # "Clocks", "I/O", etc.
    icon: str                 # emoji for display
    items: List[CoverageItem] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def covered(self) -> int:
        return sum(1 for i in self.items if i.present)

    @property
    def missing(self) -> int:
        return self.total - self.covered

    @property
    def score(self) -> float:
        return (self.covered / self.total * 100) if self.total else 0.0

    @property
    def status(self) -> str:
        """'good' | 'warn' | 'bad'"""
        if self.score >= 80:
            return "good"
        if self.score >= 50:
            return "warn"
        return "bad"


@dataclass
class CoverageResult:
    """Full coverage analysis result."""
    filename: str
    categories: List[CoverageCategory] = field(default_factory=list)
    total_items: int = 0
    total_present: int = 0
    total_missing: int = 0
    score: float = 0.0
    stats: Dict[str, object] = field(default_factory=dict)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _grab(text: str, pattern: str) -> List[str]:
    return re.findall(pattern, text, re.MULTILINE)


def _item(name: str, cmd: str, found: bool, detail: str = "", critical: bool = True) -> CoverageItem:
    return CoverageItem(name=name, cmd=cmd, present=found, detail=detail, is_critical=critical)


# ── Analyzer ─────────────────────────────────────────────────────────────────

def parse_sdc_coverage(text: str, filename: str = "") -> CoverageResult:
    """Analyze SDC text and return a CoverageResult with all categories."""
    result = CoverageResult(filename=filename)

    # ── 1. Clocks ────────────────────────────────────────────────────────────
    clocks = _grab(text, r'create_clock[^;\n]*')
    gen_clocks = _grab(text, r'create_generated_clock[^;\n]*')
    clk_latency = _grab(text, r'set_clock_latency[^;\n]*')
    clk_transition = _grab(text, r'set_clock_transition[^;\n]*')
    clk_uncertainty = _grab(text, r'set_clock_uncertainty[^;\n]*')
    clk_jitter = _grab(text, r'set_clock_jitter[^;\n]*')
    propagated = _grab(text, r'set_propagated_clock[^;\n]*')
    clk_groups = _grab(text, r'set_clock_groups[^;\n]*')
    clk_gating = _grab(text, r'set_clock_gating_check[^;\n]*')

    clock_category = CoverageCategory(name="Clocks", icon="🕐", items=[
        _item("Primary clock (create_clock)", "create_clock",
              len(clocks) > 0,
              f"{len(clocks)} defined" if clocks else "No clock defined — all paths unconstrained",
              critical=True),
        _item("Generated clock", "create_generated_clock",
              len(gen_clocks) > 0,
              f"{len(gen_clocks)} defined" if gen_clocks else "No generated clocks (OK if not needed)",
              critical=False),
        _item("Clock latency", "set_clock_latency",
              len(clk_latency) > 0,
              f"{len(clk_latency)} set" if clk_latency else "Missing — model insertion delay for pre-CTS",
              critical=False),
        _item("Clock transition", "set_clock_transition",
              len(clk_transition) > 0,
              f"{len(clk_transition)} set" if clk_transition else "Missing — constrain clock slew",
              critical=False),
        _item("Clock uncertainty", "set_clock_uncertainty",
              len(clk_uncertainty) > 0,
              f"{len(clk_uncertainty)} set" if clk_uncertainty else "Missing — no jitter/margin modeled",
              critical=True),
        _item("Clock jitter", "set_clock_jitter",
              len(clk_jitter) > 0,
              f"{len(clk_jitter)} set" if clk_jitter else "Missing — separate random jitter from uncertainty",
              critical=False),
        _item("Propagated clock", "set_propagated_clock",
              len(propagated) > 0,
              f"{len(propagated)} set" if propagated else "Missing — ideal clock is over-optimistic",
              critical=True),
        _item("Clock groups", "set_clock_groups",
              len(clk_groups) > 0,
              f"{len(clk_groups)} set" if clk_groups else "Missing — CDC paths may be analyzed as synchronous",
              critical=len(clocks) > 1),
        _item("Clock gating check", "set_clock_gating_check",
              len(clk_gating) > 0,
              f"{len(clk_gating)} set" if clk_gating else "Missing — needed if design uses clock gating",
              critical=False),
    ])
    result.categories.append(clock_category)

    # ── 2. I/O ───────────────────────────────────────────────────────────────
    input_delay = _grab(text, r'set_input_delay[^;\n]*')
    output_delay = _grab(text, r'set_output_delay[^;\n]*')
    driving_cell = _grab(text, r'set_driving_cell[^;\n]*')
    input_trans = _grab(text, r'set_input_transition[^;\n]*')
    load = _grab(text, r'set_load[^;\n]*')
    drive = _grab(text, r'set_drive[^;\n]*')

    # Check for -min variants
    has_input_min = any('-min' in d for d in input_delay)
    has_output_min = any('-min' in d for d in output_delay)

    io_category = CoverageCategory(name="I/O Constraints", icon="🔌", items=[
        _item("Input delay (max)", "set_input_delay",
              len(input_delay) > 0,
              f"{len(input_delay)} set" if input_delay else "Missing — input ports unconstrained",
              critical=True),
        _item("Input delay (min / hold)", "set_input_delay -min",
              has_input_min,
              "Has -min" if has_input_min else "Missing -min — hold timing unchecked",
              critical=True),
        _item("Output delay (max)", "set_output_delay",
              len(output_delay) > 0,
              f"{len(output_delay)} set" if output_delay else "Missing — output ports unconstrained",
              critical=True),
        _item("Output delay (min / hold)", "set_output_delay -min",
              has_output_min,
              "Has -min" if has_output_min else "Missing -min — output hold unchecked",
              critical=True),
        _item("Driving cell / input transition", "set_driving_cell",
              len(driving_cell) > 0 or len(input_trans) > 0 or len(drive) > 0,
              f"driving_cell={len(driving_cell)}, transition={len(input_trans)}, drive={len(drive)}"
              if (driving_cell or input_trans or drive) else "Missing — input slew is ideal",
              critical=False),
        _item("Output load", "set_load",
              len(load) > 0,
              f"{len(load)} set" if load else "Missing — output capacitance unconstrained",
              critical=False),
    ])
    result.categories.append(io_category)

    # ── 3. Timing Exceptions ─────────────────────────────────────────────────
    false_paths = _grab(text, r'set_false_path[^;\n]*')
    mc_paths = _grab(text, r'set_multicycle_path[^;\n]*')
    max_delay = _grab(text, r'set_max_delay[^;\n]*')
    min_delay = _grab(text, r'set_min_delay[^;\n]*')
    group_path = _grab(text, r'group_path[^;\n]*')
    disable_timing = _grab(text, r'set_disable_timing[^;\n]*')

    # Check if multicycle has hold counterparts
    mc_setup = [m for m in mc_paths if '-setup' in m or re.search(r'set_multicycle_path\s+\d+', m)]
    mc_hold = [m for m in mc_paths if '-hold' in m]
    has_mc_hold_fix = len(mc_hold) > 0 if mc_setup else True  # no setup = no hold needed

    exc_category = CoverageCategory(name="Timing Exceptions", icon="⚠️", items=[
        _item("False paths", "set_false_path",
              len(false_paths) > 0,
              f"{len(false_paths)} defined" if false_paths else "None defined — all paths timing-analyzed",
              critical=False),
        _item("Multicycle paths", "set_multicycle_path",
              len(mc_paths) > 0,
              f"{len(mc_paths)} defined" if mc_paths else "None defined — all paths single-cycle",
              critical=False),
        _item("Multicycle hold fix", "set_multicycle_path -hold",
              has_mc_hold_fix,
              "Hold counterparts present" if has_mc_hold_fix else "Missing — multicycle without hold fix",
              critical=len(mc_paths) > 0),
        _item("Max delay", "set_max_delay",
              len(max_delay) > 0,
              f"{len(max_delay)} set" if max_delay else "None — use for path-specific max constraints",
              critical=False),
        _item("Min delay", "set_min_delay",
              len(min_delay) > 0,
              f"{len(min_delay)} set" if min_delay else "None — use for path-specific min constraints",
              critical=False),
        _item("Group paths", "group_path",
              len(group_path) > 0,
              f"{len(group_path)} set" if group_path else "Missing — improves synthesis optimization focus",
              critical=False),
        _item("Disable timing arcs", "set_disable_timing",
              len(disable_timing) > 0,
              f"{len(disable_timing)} set" if disable_timing else "None — all cell timing arcs active",
              critical=False),
    ])
    result.categories.append(exc_category)

    # ── 4. Design Rules ──────────────────────────────────────────────────────
    max_fanout = _grab(text, r'set_max_fanout[^;\n]*')
    max_trans = _grab(text, r'set_max_transition[^;\n]*')
    max_cap = _grab(text, r'set_max_capacitance[^;\n]*')
    min_cap = _grab(text, r'set_min_capacitance[^;\n]*')
    max_area = _grab(text, r'set_max_area[^;\n]*')
    sdc_version = _grab(text, r'set\s+sdc_version[^;\n]*')
    set_units = _grab(text, r'set_units[^;\n]*')

    dr_category = CoverageCategory(name="Design Rules", icon="📏", items=[
        _item("SDC version", "set sdc_version",
              len(sdc_version) > 0,
              "Declared" if sdc_version else "Missing — add 'set sdc_version 2.2'",
              critical=False),
        _item("Units", "set_units",
              len(set_units) > 0,
              "Declared" if set_units else "Missing — add set_units to avoid unit mismatches",
              critical=False),
        _item("Max fanout", "set_max_fanout",
              len(max_fanout) > 0,
              f"{len(max_fanout)} set" if max_fanout else "Missing — no fanout limit",
              critical=True),
        _item("Max transition", "set_max_transition",
              len(max_trans) > 0,
              f"{len(max_trans)} set" if max_trans else "Missing — no slew limit",
              critical=True),
        _item("Max capacitance", "set_max_capacitance",
              len(max_cap) > 0,
              f"{len(max_cap)} set" if max_cap else "Missing — no capacitance limit",
              critical=False),
        _item("Max area", "set_max_area",
              len(max_area) > 0,
              f"set" if max_area else "Missing — no area target for synthesis",
              critical=False),
    ])
    result.categories.append(dr_category)

    # ── 5. AOCV / Derate ────────────────────────────────────────────────────
    timing_derate = _grab(text, r'set_timing_derate[^;\n]*')
    oper_cond = _grab(text, r'set_operating_conditions[^;\n]*')
    wire_load_mode = _grab(text, r'set_wire_load_mode[^;\n]*')
    wire_load_model = _grab(text, r'set_wire_load_model[^;\n]*')

    # Check derate completeness
    has_early = any('-early' in t for t in timing_derate)
    has_late = any('-late' in t for t in timing_derate)
    has_cell = any('-cell_delay' in t for t in timing_derate)
    has_net = any('-net_delay' in t for t in timing_derate)

    aocv_category = CoverageCategory(name="AOCV / Derate", icon="📊", items=[
        _item("Timing derate", "set_timing_derate",
              len(timing_derate) > 0,
              f"{len(timing_derate)} set" if timing_derate else "Missing — needed for AOCV/POCVM signoff",
              critical=True),
        _item("Derate early + late", "set_timing_derate -early/-late",
              has_early and has_late,
              f"early={has_early}, late={has_late}" if timing_derate else "No derate",
              critical=len(timing_derate) > 0),
        _item("Derate cell + net", "set_timing_derate -cell_delay/-net_delay",
              has_cell and has_net,
              f"cell={has_cell}, net={has_net}" if timing_derate else "No derate",
              critical=len(timing_derate) > 0),
        _item("Operating conditions", "set_operating_conditions",
              len(oper_cond) > 0,
              f"{len(oper_cond)} set" if oper_cond else "Missing — PVT corner not specified",
              critical=True),
        _item("Wire load mode", "set_wire_load_mode",
              len(wire_load_mode) > 0,
              f"set" if wire_load_mode else "Missing — legacy wire load model",
              critical=False),
    ])
    result.categories.append(aocv_category)

    # ── 6. Power / DFT ──────────────────────────────────────────────────────
    max_dyn = _grab(text, r'set_max_dynamic_power[^;\n]*')
    max_leak = _grab(text, r'set_max_leakage_power[^;\n]*')
    case_analysis = _grab(text, r'set_case_analysis[^;\n]*')
    dont_use = _grab(text, r'set_dont_use[^;\n]*')
    dont_touch = _grab(text, r'set_dont_touch[^;\n]*')
    ideal_network = _grab(text, r'set_ideal_network[^;\n]*')
    min_pulse = _grab(text, r'set_min_pulse_width[^;\n]*')

    pwr_category = CoverageCategory(name="Power / DFT", icon="⚡", items=[
        _item("Max dynamic power", "set_max_dynamic_power",
              len(max_dyn) > 0,
              f"set" if max_dyn else "Missing — no power budget",
              critical=False),
        _item("Max leakage power", "set_max_leakage_power",
              len(max_leak) > 0,
              f"set" if max_leak else "Missing — no leakage budget",
              critical=False),
        _item("Case analysis (DFT)", "set_case_analysis",
              len(case_analysis) > 0,
              f"{len(case_analysis)} set" if case_analysis else "Missing — DFT paths not isolated",
              critical=False),
        _item("Dont-use cells", "set_dont_use",
              len(dont_use) > 0,
              f"{len(dont_use)} set" if dont_use else "Missing — no cell exclusion",
              critical=False),
        _item("Ideal network", "set_ideal_network",
              len(ideal_network) > 0,
              f"set" if ideal_network else "Missing — reset/scan_en not marked ideal",
              critical=False),
        _item("Min pulse width", "set_min_pulse_width",
              len(min_pulse) > 0,
              f"set" if min_pulse else "Missing — narrow pulses may cause metastability",
              critical=False),
    ])
    result.categories.append(pwr_category)

    # ── Totals ───────────────────────────────────────────────────────────────
    result.total_items = sum(c.total for c in result.categories)
    result.total_present = sum(c.covered for c in result.categories)
    result.total_missing = sum(c.missing for c in result.categories)
    result.score = (result.total_present / result.total_items * 100) if result.total_items else 0.0

    result.stats = {
        "categories": len(result.categories),
        "total_items": result.total_items,
        "present": result.total_present,
        "missing": result.total_missing,
        "score_pct": round(result.score, 1),
    }

    return result
