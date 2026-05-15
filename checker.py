"""
SDC Constraint Checker
Validates SDC files and reports errors, warnings, and best-practice suggestions.
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class Issue:
    sev: str       # "error" | "warning"
    code: str
    msg: str


@dataclass
class InfoItem:
    code: str
    msg: str


@dataclass
class CheckResult:
    issues: List[Issue] = field(default_factory=list)
    info: List[InfoItem] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)

    @property
    def errors(self):
        return [i for i in self.issues if i.sev == "error"]

    @property
    def warnings(self):
        return [i for i in self.issues if i.sev == "warning"]


def _grab(text: str, pattern: str) -> List[str]:
    return re.findall(pattern, text, re.MULTILINE)


def check_sdc(text: str) -> CheckResult:
    result = CheckResult()
    issues = result.issues
    info   = result.info

    # ── Grab all commands ─────────────────────────────────────────────────────
    clocks          = _grab(text, r'create_clock[^;\n]*')
    gen_clocks      = _grab(text, r'create_generated_clock[^;\n]*')
    group_path      = _grab(text, r'group_path[^;\n]*')
    clk_gating_chk  = _grab(text, r'set_clock_gating_check[^;\n]*')
    clk_groups      = _grab(text, r'set_clock_groups[^;\n]*')
    clk_jitter      = _grab(text, r'set_clock_jitter[^;\n]*')
    clk_latency     = _grab(text, r'set_clock_latency[^;\n]*')
    clk_transition  = _grab(text, r'set_clock_transition[^;\n]*')
    clk_uncertainty = _grab(text, r'set_clock_uncertainty[^;\n]*')
    data_check      = _grab(text, r'set_data_check[^;\n]*')
    disable_timing  = _grab(text, r'set_disable_timing[^;\n]*')
    false_paths     = _grab(text, r'set_false_path[^;\n]*')
    ideal_network   = _grab(text, r'set_ideal_network[^;\n]*')
    input_delay     = _grab(text, r'set_input_delay[^;\n]*')
    min_pulse_width = _grab(text, r'set_min_pulse_width[^;\n]*')
    output_delay    = _grab(text, r'set_output_delay[^;\n]*')
    propagated      = _grab(text, r'set_propagated_clock[^;\n]*')
    timing_derate   = _grab(text, r'set_timing_derate[^;\n]*')
    max_delay       = _grab(text, r'set_max_delay[^;\n]*')
    min_delay       = _grab(text, r'set_min_delay[^;\n]*')
    mc_paths        = _grab(text, r'set_multicycle_path[^;\n]*')
    case_analysis   = _grab(text, r'set_case_analysis[^;\n]*')
    drive           = _grab(text, r'set_drive[^;\n]*')
    driving_cell    = _grab(text, r'set_driving_cell[^;\n]*')
    input_transition= _grab(text, r'set_input_transition[^;\n]*')
    load            = _grab(text, r'set_load[^;\n]*')
    max_area        = _grab(text, r'set_max_area[^;\n]*')
    max_cap         = _grab(text, r'set_max_capacitance[^;\n]*')
    max_fanout      = _grab(text, r'set_max_fanout[^;\n]*')
    max_trans       = _grab(text, r'set_max_transition[^;\n]*')
    oper_cond       = _grab(text, r'set_operating_conditions[^;\n]*')
    wire_load_mode  = _grab(text, r'set_wire_load_mode[^;\n]*')
    wire_load_model = _grab(text, r'set_wire_load_model[^;\n]*')
    dont_touch      = _grab(text, r'set_dont_touch[^;\n]*')
    dont_use        = _grab(text, r'set_dont_use[^;\n]*')
    sdc_version     = _grab(text, r'set\s+sdc_version[^;\n]*')
    set_units       = _grab(text, r'set_units[^;\n]*')
    max_dyn_power   = _grab(text, r'set_max_dynamic_power[^;\n]*')
    max_leak_power  = _grab(text, r'set_max_leakage_power[^;\n]*')
    voltage         = _grab(text, r'set_voltage[^;\n]*')
    voltage_area    = _grab(text, r'create_voltage_area[^;\n]*')

    virtual_clocks = [c for c in clocks if '[get_ports' not in c and '[get_pins' not in c]

    # ── ERRORS ────────────────────────────────────────────────────────────────
    if not clocks and not gen_clocks:
        issues.append(Issue("error", "SDC-001",
            "No create_clock defined. Synthesis has no timing reference — all paths are unconstrained."))

    # Duplicate clock names
    clock_names = [m for c in clocks if (m := re.search(r'-name\s+(\S+)', c)) and (m := m.group(1))]
    seen, dupes = set(), set()
    for n in clock_names:
        if n in seen:
            dupes.add(n)
        seen.add(n)
    for n in dupes:
        issues.append(Issue("error", "SDC-002",
            f'Duplicate clock name "{n}" — two create_clock commands use the same name.'))

    # Generated clock missing -source
    for gc in gen_clocks:
        if '-source' not in gc:
            issues.append(Issue("error", "SDC-003",
                f'create_generated_clock missing required -source: "{gc[:70]}…"'))
        if '-divide_by' in gc and '-multiply_by' in gc:
            issues.append(Issue("error", "SDC-004",
                f'create_generated_clock has both -divide_by and -multiply_by — use one only.'))

    if not input_delay and clocks:
        issues.append(Issue("error", "SDC-005",
            "No set_input_delay — all input ports are unconstrained."))
    if not output_delay and clocks:
        issues.append(Issue("error", "SDC-006",
            "No set_output_delay — all output ports are unconstrained."))

    for c in clocks:
        port_m = re.search(r'\[get_ports\s+([^\]]+)\]', c)
        if port_m and re.search(r'\b(data|addr|bus|wdata|rdata|din|dout)\b', port_m.group(1), re.I):
            issues.append(Issue("error", "SDC-007",
                f'create_clock on likely data port "{port_m.group(1)}" — use dedicated clock ports only.'))

    for c in clocks:
        per_m = re.search(r'-period\s+([\d.]+)', c)
        if not per_m:
            continue
        period = float(per_m.group(1))
        for id_ in input_delay:
            v = re.search(r'set_input_delay\s+([\d.]+)', id_)
            if v and float(v.group(1)) >= period:
                issues.append(Issue("error", "SDC-008",
                    f'set_input_delay {v.group(1)}ns >= clock period {period}ns — timing closure impossible.'))
        for od in output_delay:
            v = re.search(r'set_output_delay\s+([\d.]+)', od)
            if v and float(v.group(1)) >= period:
                issues.append(Issue("error", "SDC-009",
                    f'set_output_delay {v.group(1)}ns >= clock period {period}ns — no margin for output logic.'))

    for vc in virtual_clocks:
        name_m = re.search(r'-name\s+(\S+)', vc)
        if name_m:
            name = name_m.group(1)
            if any(name in p for p in propagated):
                issues.append(Issue("error", "SDC-010",
                    f'set_propagated_clock applied to virtual clock "{name}" — virtual clocks have no physical source.'))

    for ca in case_analysis:
        val_m = re.search(r'set_case_analysis\s+(\S+)', ca)
        if val_m:
            val = val_m.group(1).lower()
            if val not in ('0', '1', 'rising', 'falling', 'rise', 'fall'):
                issues.append(Issue("error", "SDC-011",
                    f'set_case_analysis invalid value "{val_m.group(1)}" — allowed: 0, 1, rising, falling.'))

    # ── WARNINGS ──────────────────────────────────────────────────────────────
    for fp in false_paths:
        if not re.search(r'-from.*async|-to.*async|-through.*scan|-from.*test', fp, re.I):
            f_m = re.search(r'-from\s+(\S+)', fp)
            t_m = re.search(r'-to\s+(\S+)', fp)
            if f_m and t_m:
                issues.append(Issue("warning", "SDC-020",
                    f'set_false_path from {f_m.group(1)} to {t_m.group(1)} — confirm this is a genuine false path.'))

    for mc in mc_paths:
        s_m = re.search(r'-setup\s+(\d+)', mc) or re.search(r'set_multicycle_path\s+(\d+)', mc)
        if s_m and int(s_m.group(1)) > 1 and '-hold' not in mc:
            issues.append(Issue("warning", "SDC-021",
                f'Multicycle path -setup {s_m.group(1)} has no -hold fix. Add -hold {int(s_m.group(1))-1}.'))

    for u in clk_uncertainty:
        v_m = re.search(r'set_clock_uncertainty\s+([\d.]+)', u)
        if v_m:
            v = float(v_m.group(1))
            if v < 0.05:
                issues.append(Issue("warning", "SDC-022",
                    f'Clock uncertainty {v}ns is unrealistically tight — below 0.05ns causes over-optimization.'))
            if v > 0.5:
                issues.append(Issue("warning", "SDC-023",
                    f'Clock uncertainty {v}ns is very high (>0.5ns). Verify this is intentional.'))

    if len(clocks) > 1 and not clk_groups:
        issues.append(Issue("warning", "SDC-024",
            f'{len(clocks)} clocks defined but no set_clock_groups — CDC paths may be analyzed as synchronous.'))

    for dt in dont_touch:
        if re.search(r'\[all_cells\]|\*', dt):
            issues.append(Issue("warning", "SDC-025",
                'set_dont_touch with wildcard — blocks all optimization and degrades QoR significantly.'))

    for mt in max_trans:
        v_m = re.search(r'set_max_transition\s+([\d.]+)', mt)
        if v_m and float(v_m.group(1)) < 0.05:
            issues.append(Issue("warning", "SDC-026",
                f'set_max_transition {v_m.group(1)}ns extremely tight — may be unachievable.'))

    for md in max_delay:
        if '-datapath_only' not in md:
            issues.append(Issue("warning", "SDC-027",
                'set_max_delay without -datapath_only — hold constraints on same path may be violated.'))

    if input_delay and not any('-min' in i for i in input_delay):
        issues.append(Issue("warning", "SDC-028",
            'No set_input_delay -min — hold timing at input ports cannot be checked.'))
    if output_delay and not any('-min' in o for o in output_delay):
        issues.append(Issue("warning", "SDC-029",
            'No set_output_delay -min — hold timing at output ports is unconstrained.'))

    if clocks and not propagated:
        issues.append(Issue("warning", "SDC-030",
            'No set_propagated_clock — ideal clock model is over-optimistic for post-layout correlation.'))

    for cg in clk_groups:
        if not re.search(r'-asynchronous|-logically_exclusive|-physically_exclusive', cg):
            issues.append(Issue("warning", "SDC-031",
                'set_clock_groups without -asynchronous/-logically_exclusive/-physically_exclusive.'))

    if timing_derate:
        has_early = any('-early' in t for t in timing_derate)
        has_late  = any('-late' in t for t in timing_derate)
        if has_early and not has_late:
            issues.append(Issue("warning", "SDC-032", 'set_timing_derate has -early but no -late.'))
        if has_late and not has_early:
            issues.append(Issue("warning", "SDC-033", 'set_timing_derate has -late but no -early.'))

    for dc in data_check:
        if '-clock' not in dc:
            issues.append(Issue("warning", "SDC-034", 'set_data_check without -clock reference.'))

    if len(disable_timing) > 5:
        issues.append(Issue("warning", "SDC-035",
            f'{len(disable_timing)} set_disable_timing commands — large count can hide real violations.'))
    for dt in disable_timing:
        if '-from' not in dt and '-to' not in dt:
            issues.append(Issue("warning", "SDC-036",
                'set_disable_timing without -from/-to disables ALL arcs on cell — almost always wrong.'))

    half_setup = [m for m in mc_paths if '-setup' in m and ('-rise_to' in m or '-fall_to' in m)]
    half_hold  = [m for m in mc_paths if '-hold'  in m and ('-rise_to' in m or '-fall_to' in m)]
    if half_setup and not half_hold:
        issues.append(Issue("warning", "SDC-037",
            'Half-cycle setup paths found but no matching -hold 0 counterpart. Hold analysis will be wrong.'))

    # ── INFO ──────────────────────────────────────────────────────────────────
    if not sdc_version:
        info.append(InfoItem("SDC-100", "No sdc_version declaration. Add 'set sdc_version 2.2' at the top."))
    if not set_units:
        info.append(InfoItem("SDC-101", "No set_units — add 'set_units -time ns -capacitance pF' to avoid unit mismatches."))
    if not max_fanout:
        info.append(InfoItem("SDC-102", "No set_max_fanout — consider set_max_fanout 20 [all_inputs]."))
    if not max_trans:
        info.append(InfoItem("SDC-103", "No set_max_transition — add set_max_transition 0.2 [all_nets]."))
    if not max_cap:
        info.append(InfoItem("SDC-104", "No set_max_capacitance."))
    if not load:
        info.append(InfoItem("SDC-105", "No set_load on outputs."))
    if not driving_cell and not input_transition and not drive:
        info.append(InfoItem("SDC-106", "No set_driving_cell / set_input_transition / set_drive — input slew is ideal."))
    if not clk_latency:
        info.append(InfoItem("SDC-107", "No set_clock_latency — model insertion delay with set_clock_latency -source before CTS."))
    if not clk_transition:
        info.append(InfoItem("SDC-108", "No set_clock_transition — constrain clock slew with set_clock_transition 0.1 [all_clocks]."))
    if not case_analysis:
        info.append(InfoItem("SDC-109", "No set_case_analysis — use for scan_en, test_mode to prevent DFT paths dominating timing."))
    if not ideal_network and clocks:
        info.append(InfoItem("SDC-110", "No set_ideal_network — mark reset/scan_en as ideal."))
    if len(false_paths) > 10:
        info.append(InfoItem("SDC-111", f'{len(false_paths)} set_false_path commands — audit each one is genuinely a false path.'))
    if len(mc_paths) > 8:
        info.append(InfoItem("SDC-112", f'{len(mc_paths)} set_multicycle_path commands — document each one.'))
    if not dont_use:
        info.append(InfoItem("SDC-113", "No set_dont_use — consider excluding weak/problematic cells."))
    if not oper_cond:
        info.append(InfoItem("SDC-114", "No set_operating_conditions — specify PVT corner explicitly."))
    if not timing_derate:
        info.append(InfoItem("SDC-115", "No set_timing_derate — needed for AOCV/POCVM advanced signoff."))
    if not clk_jitter:
        info.append(InfoItem("SDC-116", "No set_clock_jitter — model random jitter separately from uncertainty."))
    if not group_path:
        info.append(InfoItem("SDC-117", "No group_path — improves synthesis optimization focus on critical interfaces."))
    if not clk_gating_chk:
        info.append(InfoItem("SDC-118", "No set_clock_gating_check — needed if design uses clock gating cells."))
    if disable_timing:
        info.append(InfoItem("SDC-119", f'{len(disable_timing)} set_disable_timing found — verify each is intentional.'))
    if min_delay:
        info.append(InfoItem("SDC-120", f'{len(min_delay)} set_min_delay — verify no conflicts with hold constraints.'))
    if not wire_load_mode and not wire_load_model:
        info.append(InfoItem("SDC-121", "No wire load constraints — needed for flows without extracted RC."))
    if not max_area:
        info.append(InfoItem("SDC-122", "No set_max_area — add area target for synthesis."))
    if not max_dyn_power and not max_leak_power:
        info.append(InfoItem("SDC-123", "No power constraints."))
    if not min_pulse_width and clk_gating_chk:
        info.append(InfoItem("SDC-124", "set_clock_gating_check present but no set_min_pulse_width."))
    if voltage and not voltage_area:
        info.append(InfoItem("SDC-125", "set_voltage found but no create_voltage_area."))
    if virtual_clocks:
        info.append(InfoItem("SDC-126",
            f'{len(virtual_clocks)} virtual clock(s) detected — ensure set_input_delay/set_output_delay references them correctly.'))

    result.stats = {
        "Clocks":          len(clocks),
        "Generated clocks":len(gen_clocks),
        "Virtual clocks":  len(virtual_clocks),
        "Input delays":    len(input_delay),
        "Output delays":   len(output_delay),
        "False paths":     len(false_paths),
        "Multicycle paths":len(mc_paths),
        "Clock groups":    len(clk_groups),
        "Uncertainty":     len(clk_uncertainty),
        "Clk transition":  len(clk_transition),
        "Clk jitter":      len(clk_jitter),
        "Max transition":  len(max_trans),
        "Max cap":         len(max_cap),
        "Case analysis":   len(case_analysis),
        "Disable arcs":    len(disable_timing),
        "Timing derate":   len(timing_derate),
        "Oper conditions": len(oper_cond),
        "Group paths":     len(group_path),
        "Propagated":      len(propagated),
    }
    return result
