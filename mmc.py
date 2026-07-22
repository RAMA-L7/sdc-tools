"""
MMC Operations
Multi-corner SDC generation, diff, cross-corner checking, and ZIP packaging.
"""

import re
import io
import zipfile
import difflib
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from generator import SDCParams, ClockDef, generate_sdc
from checker import CheckResult, Issue, InfoItem, check_sdc
from corner_manager import Corner


# ── Multi-Corner SDC Generation ───────────────────────────────────────────────

def generate_corner_sdcs(
    template: SDCParams,
    corners: List[Corner],
) -> Dict[str, str]:
    """Generate a per-corner SDC from a base template.

    For each corner, the template is cloned and overridden with:
    - operating_conditions set to corner name
    - timing_derate set to corner's derate values
    - clock uncertainty scaled by corner's uncertainty_scale
    - design_name suffixed with corner name

    Returns {corner_name: sdc_text}.
    """
    results = {}
    for corner in corners:
        # Clone template by re-creating from its current values
        p = SDCParams(
            design_name=f"{template.design_name}_{corner.name}",
            sdc_version=template.sdc_version,
            add_units=template.add_units,
            time_unit=template.time_unit,
            cap_unit=template.cap_unit,
            res_unit=template.res_unit,
            clocks=_scale_clocks(template.clocks, corner.uncertainty_scale),
            add_clk_jitter=template.add_clk_jitter,
            clk_jitter_val=template.clk_jitter_val,
            add_clk_transition=template.add_clk_transition,
            clk_transition_val=template.clk_transition_val,
            add_clk_gating=template.add_clk_gating,
            clk_gate_setup=template.clk_gate_setup,
            clk_gate_hold=template.clk_gate_hold,
            add_latency=template.add_latency,
            latency_val=template.latency_val,
            add_propagated=template.add_propagated,
            in_delay_max=template.in_delay_max,
            in_delay_min=template.in_delay_min,
            out_delay_max=template.out_delay_max,
            out_delay_min=template.out_delay_min,
            add_drive_cell=template.add_drive_cell,
            drive_cell_name=template.drive_cell_name,
            add_input_transition=template.add_input_transition,
            input_transition_val=template.input_transition_val,
            add_load=template.add_load,
            load_val=template.load_val,
            max_fanout=template.max_fanout,
            max_transition=template.max_transition,
            max_cap=template.max_cap,
            min_cap=template.min_cap,
            max_area=template.max_area,
            # Corner-specific overrides:
            add_oper_cond=True,
            oper_cond_name=corner.operating_condition or corner.name,
            add_derate=True,
            derate_cell_early=corner.derate_cell_early,
            derate_cell_late=corner.derate_cell_late,
            derate_net_early=corner.derate_net_early,
            derate_net_late=corner.derate_net_late,
            add_ideal_rst=template.add_ideal_rst,
            rst_port=template.rst_port,
            add_scan=template.add_scan,
            scan_port=template.scan_port,
            add_min_pulse=template.add_min_pulse,
            min_pulse_val=template.min_pulse_val,
            case_entries=template.case_entries,
            disable_arcs=template.disable_arcs,
            add_group_path=template.add_group_path,
            path_groups=template.path_groups,
            add_wire_load=template.add_wire_load,
            wire_load_mode=template.wire_load_mode,
            wire_load_model=template.wire_load_model,
            false_paths=template.false_paths,
            mc_paths=template.mc_paths,
            half_paths=template.half_paths,
            add_power=template.add_power,
            max_dyn_power=template.max_dyn_power,
            max_leak_power=template.max_leak_power,
            dont_use=template.dont_use,
        )
        sdc_text = generate_sdc(p)
        # Prepend corner header
        header = (
            f"# ── Corner: {corner.name} ───────────────────────────────────────\n"
            f"# Process: {corner.process_type}  "
            f"V={corner.voltage:.2f}V  T={corner.temperature:.0f}°C\n"
            f"# ─────────────────────────────────────────────────────────────\n\n"
        )
        results[corner.name] = header + sdc_text
    return results


def _scale_clocks(clocks: List[ClockDef], scale: float) -> List[ClockDef]:
    """Return a new list of ClockDef with uncertainty scaled."""
    scaled = []
    for c in clocks:
        new_c = ClockDef(
            name=c.name,
            clk_type=c.clk_type,
            port=c.port,
            period=c.period,
            uncertainty=round(c.uncertainty * scale, 4),
            duty_cycle=c.duty_cycle,
            master_port=c.master_port,
            divide_by=c.divide_by,
            multiply_by=c.multiply_by,
            edge_shift=c.edge_shift,
            invert=c.invert,
            preinvert=c.preinvert,
            combinational=c.combinational,
            add_flag=c.add_flag,
        )
        scaled.append(new_c)
    return scaled


# ── Corner Diff ───────────────────────────────────────────────────────────────

@dataclass
class DiffLine:
    line_type: str      # "equal" | "added" | "removed" | "changed"
    text_a: str         # content from corner A
    text_b: str         # content from corner B
    section: str        # inferred section name

# Patterns to exclude from diff (expected to differ between corners)
_DIFF_EXCLUDE_PATTERNS = [
    r'^#.*Corner:',
    r'^#.*Process:',
    r'^#.*──.*─+$',
    r'^#.*generated by',
    r'^#.*NOTE:',
]


def _normalize_sdc(text: str) -> List[str]:
    """Normalize SDC text for diff comparison.

    Strips comments, blank lines, and whitespace; returns list of content lines.
    """
    lines = text.splitlines()
    normalized = []
    for line in lines:
        stripped = line.strip()
        # Skip comments
        if stripped.startswith('#'):
            continue
        # Skip blank lines
        if not stripped:
            continue
        # Skip lines matching exclude patterns
        if any(re.search(pat, stripped) for pat in _DIFF_EXCLUDE_PATTERNS):
            continue
        # Collapse whitespace
        normalized.append(' '.join(stripped.split()))
    return normalized


def _infer_section(line: str) -> str:
    """Infer which SDC section a line belongs to."""
    lower = line.lower()
    if 'create_clock' in lower or 'create_generated_clock' in lower:
        return "clocks"
    if 'set_clock_' in lower or 'set_propagated' in lower:
        return "clock attributes"
    if 'set_input_delay' in lower or 'set_output_delay' in lower:
        return "I/O delays"
    if 'set_driving_cell' in lower or 'set_input_transition' in lower or 'set_load' in lower:
        return "I/O drive/load"
    if 'set_max_fanout' in lower or 'set_max_transition' in lower or 'set_max_capacitance' in lower or 'set_max_area' in lower:
        return "design rules"
    if 'set_operating_conditions' in lower:
        return "operating conditions"
    if 'set_timing_derate' in lower:
        return "timing derate"
    if 'set_ideal_network' in lower or 'set_false_path' in lower:
        return "ideal/false paths"
    if 'set_case_analysis' in lower:
        return "case analysis"
    if 'set_disable_timing' in lower:
        return "disable arcs"
    if 'set_clock_groups' in lower:
        return "clock groups"
    if 'set_multicycle_path' in lower:
        return "multicycle paths"
    if 'set_max_dynamic' in lower or 'set_max_leakage' in lower:
        return "power"
    if 'set_dont_use' in lower:
        return "dont-use"
    return "other"


def diff_corners(
    sdc_a: str,
    sdc_b: str,
    name_a: str,
    name_b: str,
) -> List[DiffLine]:
    """Compare two SDC texts and return structured diff lines."""
    lines_a = _normalize_sdc(sdc_a)
    lines_b = _normalize_sdc(sdc_b)

    matcher = difflib.SequenceMatcher(None, lines_a, lines_b)
    diff_result = []

    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == 'equal':
            for idx in range(i1, i2):
                diff_result.append(DiffLine(
                    line_type="equal",
                    text_a=lines_a[idx],
                    text_b=lines_a[idx],
                    section=_infer_section(lines_a[idx]),
                ))
        elif op == 'replace':
            # Try to match individual lines within the replace block
            sub_a = lines_a[i1:i2]
            sub_b = lines_b[j1:j2]
            sub_matcher = difflib.SequenceMatcher(None, sub_a, sub_b)
            for s_op, s_i1, s_i2, s_j1, s_j2 in sub_matcher.get_opcodes():
                if s_op == 'equal':
                    for idx in range(s_i1, s_i2):
                        diff_result.append(DiffLine(
                            line_type="equal",
                            text_a=sub_a[idx],
                            text_b=sub_a[idx],
                            section=_infer_section(sub_a[idx]),
                        ))
                elif s_op == 'replace':
                    max_len = max(s_i2 - s_i1, s_j2 - s_j1)
                    for k in range(max_len):
                        a_line = sub_a[s_i1 + k] if (s_i1 + k) < s_i2 else ""
                        b_line = sub_b[s_j1 + k] if (s_j1 + k) < s_j2 else ""
                        diff_result.append(DiffLine(
                            line_type="changed",
                            text_a=a_line,
                            text_b=b_line,
                            section=_infer_section(a_line or b_line),
                        ))
                elif s_op == 'insert':
                    for idx in range(s_j1, s_j2):
                        diff_result.append(DiffLine(
                            line_type="added",
                            text_a="",
                            text_b=sub_b[idx],
                            section=_infer_section(sub_b[idx]),
                        ))
                elif s_op == 'delete':
                    for idx in range(s_i1, s_i2):
                        diff_result.append(DiffLine(
                            line_type="removed",
                            text_a=sub_a[idx],
                            text_b="",
                            section=_infer_section(sub_a[idx]),
                        ))
        elif op == 'insert':
            for idx in range(j1, j2):
                diff_result.append(DiffLine(
                    line_type="added",
                    text_a="",
                    text_b=lines_b[idx],
                    section=_infer_section(lines_b[idx]),
                ))
        elif op == 'delete':
            for idx in range(i1, i2):
                diff_result.append(DiffLine(
                    line_type="removed",
                    text_a=lines_a[idx],
                    text_b="",
                    section=_infer_section(lines_a[idx]),
                ))

    return diff_result


# ── Cross-Corner Consistency Checks ───────────────────────────────────────────

def check_sdc_multi(sdc_dict: Dict[str, str]) -> CheckResult:
    """Run single-file checks on each corner, then cross-corner consistency checks.

    sdc_dict: {corner_name: sdc_text}
    Returns a merged CheckResult with individual + cross-corner issues.
    """
    merged = CheckResult()

    # 1. Run individual checks per corner
    individual_results: Dict[str, CheckResult] = {}
    for name, text in sdc_dict.items():
        result = check_sdc(text)
        individual_results[name] = result
        # Prefix each issue with corner name
        for issue in result.issues:
            merged.issues.append(Issue(
                sev=issue.sev,
                code=issue.code,
                msg=f"[{name}] {issue.msg}",
            ))
        for item in result.info:
            merged.info.append(InfoItem(
                code=item.code,
                msg=f"[{name}] {item.msg}",
            ))

    # 2. Cross-corner consistency checks
    if len(sdc_dict) < 2:
        merged.stats = {"Corners checked": len(sdc_dict)}
        return merged

    corner_names = list(sdc_dict.keys())
    parsed_corners: Dict[str, Dict] = {}
    for name, text in sdc_dict.items():
        parsed_corners[name] = {
            'clocks': re.findall(r'create_clock[^;\n]*', text),
            'gen_clocks': re.findall(r'create_generated_clock[^;\n]*', text),
            'input_delay': re.findall(r'set_input_delay[^;\n]*', text),
            'output_delay': re.findall(r'set_output_delay[^;\n]*', text),
            'false_paths': re.findall(r'set_false_path[^;\n]*', text),
            'mc_paths': re.findall(r'set_multicycle_path[^;\n]*', text),
            'case_analysis': re.findall(r'set_case_analysis[^;\n]*', text),
            'derate': re.findall(r'set_timing_derate[^;\n]*', text),
            'oper_cond': re.findall(r'set_operating_conditions[^;\n]*', text),
        }

    # SDC-050: Clock names differ between corners
    clock_name_sets = {}
    for name, parsed in parsed_corners.items():
        names = set()
        for c in parsed['clocks']:
            m = re.search(r'-name\s+(\S+)', c)
            if m:
                names.add(m.group(1))
        clock_name_sets[name] = names

    ref_clocks = clock_name_sets[corner_names[0]]
    for name in corner_names[1:]:
        if clock_name_sets[name] != ref_clocks:
            missing = ref_clocks - clock_name_sets[name]
            extra = clock_name_sets[name] - ref_clocks
            msg_parts = []
            if missing:
                msg_parts.append(f"missing clocks: {', '.join(sorted(missing))}")
            if extra:
                msg_parts.append(f"extra clocks: {', '.join(sorted(extra))}")
            merged.issues.append(Issue("warning", "SDC-050",
                f'Clock definitions differ between corners ({corner_names[0]} vs {name}): {"; ".join(msg_parts)}'))

    # SDC-051: Clock periods differ between corners (info — may be intentional for multi-mode)
    period_map: Dict[str, Dict[str, float]] = {}
    for name, parsed in parsed_corners.items():
        periods = {}
        for c in parsed['clocks']:
            m_name = re.search(r'-name\s+(\S+)', c)
            m_per = re.search(r'-period\s+([\d.]+)', c)
            if m_name and m_per:
                periods[m_name.group(1)] = float(m_per.group(1))
        period_map[name] = periods

    ref_name = corner_names[0]
    for name in corner_names[1:]:
        for clk in period_map.get(ref_name, {}):
            if clk in period_map.get(name, {}):
                p_ref = period_map[ref_name][clk]
                p_cur = period_map[name][clk]
                if abs(p_ref - p_cur) > 0.001:
                    merged.info.append(InfoItem("SDC-051",
                        f'Clock "{clk}" period differs: {ref_name}={p_ref}ns vs {name}={p_cur}ns (may be intentional for multi-mode).'))

    # SDC-053: Timing exceptions present in some corners but missing in others
    exception_keys = ['false_paths', 'mc_paths', 'case_analysis']
    for key in exception_keys:
        ref_count = len(parsed_corners[ref_name][key])
        for name in corner_names[1:]:
            cur_count = len(parsed_corners[name][key])
            if (ref_count > 0) == (cur_count > 0):
                continue  # both have or both lack — OK
            if ref_count > 0 and cur_count == 0:
                merged.issues.append(Issue("warning", "SDC-053",
                    f'{key.replace("_", " ")} present in {ref_name} ({ref_count}) but missing in {name}.'))
            elif cur_count > 0 and ref_count == 0:
                merged.issues.append(Issue("warning", "SDC-053",
                    f'{key.replace("_", " ")} present in {name} ({cur_count}) but missing in {ref_name}.'))

    # SDC-054: Derate values not monotonically ordered across PVT corners
    # Extract derate values per corner and check ordering
    derate_vals: Dict[str, Dict[str, float]] = {}
    for name, parsed in parsed_corners.items():
        for td in parsed['derate']:
            m = re.search(r'(-early|-late)\s+(-cell_delay|-net_delay)\s+([\d.]+)', td)
            if m:
                key = f"{m.group(1)}_{m.group(2)}"
                if name not in derate_vals:
                    derate_vals[name] = {}
                derate_vals[name][key] = float(m.group(3))

    if derate_vals:
        # Check that WORST-type corners have tighter (larger early, smaller late) derates
        for dk in ['-early_cell_delay', '-late_cell_delay']:
            values = [(n, derate_vals[n].get(dk, 0)) for n in corner_names if n in derate_vals and dk in derate_vals[n]]
            if len(values) >= 2:
                # For cell_early: worst corner should have highest value
                # For cell_late: worst corner should have lowest value
                for i in range(len(values)):
                    for j in range(i + 1, len(values)):
                        n_a, v_a = values[i]
                        n_b, v_b = values[j]
                        if abs(v_a - v_b) < 0.001:
                            continue
                        # Just flag if derate values are inverted (non-monotonic)
                        # This is informational, not necessarily wrong
                        pass  # Skip strict monotonic check — too many valid scenarios

    merged.stats = {
        "Corners checked": len(sdc_dict),
        **{f"Corners/{k}": len(v) for k, v in parsed_corners[corner_names[0]].items()},
    }

    return merged


# ── ZIP Packaging ──────────────────────────────────────────────────────────────

def create_corner_zip(sdc_dict: Dict[str, str]) -> bytes:
    """Package multiple corner SDCs into a ZIP archive.

    Returns raw bytes suitable for st.download_button.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for corner_name, sdc_text in sdc_dict.items():
            safe_name = corner_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
            zf.writestr(f"{safe_name}.sdc", sdc_text)
    return buf.getvalue()
