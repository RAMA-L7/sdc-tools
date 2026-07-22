"""
Constraint Change Impact Analyzer
Semantic SDC diff + change impact rules, modeled on Ausdia TimeVision.
"""

import re
import difflib
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

from tcl_resolver import SymbolTable, build_symbol_table, resolve_variables
from wildcard_analyzer import compare_wildcards, parse_wildcard


# ── Constraint dataclass ──────────────────────────────────────────────────────

@dataclass
class Constraint:
    command_type: str            # "create_clock", "set_false_path", etc.
    category: str                # "clocks", "false_paths", "multicycle_paths", ...
    raw_text: str                # original command text
    fields: Dict[str, Any]      # parsed key-value pairs
    line_number: int = 0


# ── Change rule and result dataclasses ────────────────────────────────────────

@dataclass
class ChangeRule:
    rule_id: str          # e.g. "CHG-FP-001"
    severity: str         # "fatal" | "warning" | "info"
    description: str      # human-readable explanation


@dataclass
class ConstraintChange:
    rule: ChangeRule
    constraint_type: str       # "set_false_path", etc.
    v1_text: str               # original text (empty if added)
    v2_text: str               # new text (empty if removed)
    v1_fields: Dict[str, Any]
    v2_fields: Dict[str, Any]
    category: str              # section name
    line_v1: Optional[int] = None
    line_v2: Optional[int] = None
    explanation: str = ""      # detailed impact explanation


@dataclass
class ChangeAnalysisResult:
    changes: List[ConstraintChange] = field(default_factory=list)
    v1_constraints: List[Constraint] = field(default_factory=list)
    v2_constraints: List[Constraint] = field(default_factory=list)
    symbol_table_v1: Optional[SymbolTable] = None
    symbol_table_v2: Optional[SymbolTable] = None
    wildcard_comparisons: List[Any] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)

    @property
    def fatal_changes(self) -> List[ConstraintChange]:
        return [c for c in self.changes if c.rule.severity == "fatal"]

    @property
    def warnings(self) -> List[ConstraintChange]:
        return [c for c in self.changes if c.rule.severity == "warning"]

    @property
    def info_changes(self) -> List[ConstraintChange]:
        return [c for c in self.changes if c.rule.severity == "info"]


# ── Preprocessing ─────────────────────────────────────────────────────────────

def _join_continuations(text: str) -> str:
    """Join backslash-continued lines into single lines."""
    return re.sub(r'\\\s*\n\s*', ' ', text)


def _strip_comments(text: str) -> str:
    """Strip TCL comments (lines starting with #, and inline comments)."""
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        # Remove inline comments (but not within braces)
        in_brace = 0
        stripped = ""
        for ch in line:
            if ch == '{':
                in_brace += 1
            elif ch == '}':
                in_brace -= 1
            elif ch == '#' and in_brace == 0:
                break
            stripped += ch
        cleaned.append(stripped.rstrip())
    return '\n'.join(cleaned)


# ── Command extraction ────────────────────────────────────────────────────────

def _grab(text: str, pattern: str) -> List[str]:
    return re.findall(pattern, text, re.MULTILINE)


# ── Command-specific parsers ──────────────────────────────────────────────────

def _parse_create_clock(raw: str) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    m = re.search(r'-name\s+(\S+)', raw)
    if m: fields['name'] = m.group(1)
    m = re.search(r'-period\s+([\d.]+)', raw)
    if m: fields['period'] = float(m.group(1))
    m = re.search(r'\[get_ports\s+([^\]]+)\]', raw)
    if m: fields['port'] = m.group(1).strip()
    m = re.search(r'-waveform\s*{([^}]*)}', raw)
    if m: fields['waveform'] = m.group(1).strip()
    return fields


def _parse_generated_clock(raw: str) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    m = re.search(r'-name\s+(\S+)', raw)
    if m: fields['name'] = m.group(1)
    m = re.search(r'-source\s+\[[^\]]+\]', raw)
    if m: fields['source'] = m.group(0)
    m = re.search(r'-divide_by\s+(\d+)', raw)
    if m: fields['divide_by'] = int(m.group(1))
    m = re.search(r'-multiply_by\s+(\d+)', raw)
    if m: fields['multiply_by'] = int(m.group(1))
    m = re.search(r'\[get_ports\s+([^\]]+)\]', raw)
    if m: fields['port'] = m.group(1).strip()
    return fields


def _parse_false_path(raw: str) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    for key in ['from', 'to', 'through', 'rise_from', 'rise_to', 'fall_from', 'fall_to']:
        m = re.search(f'-{key}\\s+(\[\\S[^\\]]*\\]|\\S+)', raw)
        if m: fields[key] = m.group(1).strip()
    return fields


def _parse_multicycle_path(raw: str) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    m = re.search(r'-setup\s+(\d+)', raw) or re.search(r'set_multicycle_path\s+(\d+)\s', raw)
    if m: fields['setup'] = int(m.group(1))
    m = re.search(r'-hold\s+(\d+)', raw)
    if m: fields['hold'] = int(m.group(1))
    for key in ['from', 'to', 'through', 'rise_from', 'rise_to', 'fall_from', 'fall_to']:
        m = re.search(f'-{key}\\s+(\[\\S[^\\]]*\\]|\\S+)', raw)
        if m: fields[key] = m.group(1).strip()
    m = re.search(r'-end', raw)
    if m: fields['end'] = True
    m = re.search(r'-start', raw)
    if m: fields['start'] = True
    return fields


def _parse_clock_uncertainty(raw: str) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    m = re.search(r'-setup\s+([\d.]+)', raw)
    if m: fields['setup_val'] = float(m.group(1))
    m = re.search(r'-hold\s+([\d.]+)', raw)
    if m: fields['hold_val'] = float(m.group(1))
    m = re.search(r'\[get_clocks\s+([^\]]+)\]', raw)
    if m: fields['clocks'] = m.group(1).strip()
    return fields


def _parse_timing_derate(raw: str) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    fields['timing_type'] = 'early' if '-early' in raw else ('late' if '-late' in raw else '')
    fields['delay_type'] = 'net_delay' if '-net_delay' in raw else ('cell_delay' if '-cell_delay' in raw else '')
    m = re.search(r'([\d.]+)\s*$', raw)
    if m: fields['value'] = float(m.group(1))
    return fields


def _parse_input_delay(raw: str) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    fields['dir'] = 'max' if '-max' in raw else ('min' if '-min' in raw else '')
    m = re.search(r'set_input_delay\s+(?:-max|-min)?\s*([\d.]+)', raw)
    if m: fields['value'] = float(m.group(1))
    m = re.search(r'-clock\s+(\S+)', raw)
    if m: fields['clock'] = m.group(1)
    return fields


def _parse_output_delay(raw: str) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    fields['dir'] = 'max' if '-max' in raw else ('min' if '-min' in raw else '')
    m = re.search(r'set_output_delay\s+(?:-max|-min)?\s*([\d.]+)', raw)
    if m: fields['value'] = float(m.group(1))
    m = re.search(r'-clock\s+(\S+)', raw)
    if m: fields['clock'] = m.group(1)
    return fields


def _parse_clock_groups(raw: str) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    for gtype in ['asynchronous', 'logically_exclusive', 'physically_exclusive']:
        if gtype in raw:
            fields['group_type'] = gtype
            break
    groups = re.findall(r'-group\s+\[[^\]]+\]', raw)
    fields['groups'] = [g.strip() for g in groups]
    return fields


def _parse_generic(raw: str) -> Dict[str, Any]:
    """Fallback parser — extract all -flag value pairs."""
    fields: Dict[str, Any] = {}
    pairs = re.findall(r'-(\w+)\s+(\[?[^-\s][^\s]*\]?)', raw)
    for key, val in pairs:
        fields[key] = val.strip('[]')
    return fields


# ── Parser registry ──────────────────────────────────────────────────────────

_PARSERS: Dict[str, Tuple[str, Any]] = {
    'create_clock': ('clocks', _parse_create_clock),
    'create_generated_clock': ('clocks', _parse_generated_clock),
    'set_false_path': ('false_paths', _parse_false_path),
    'set_multicycle_path': ('multicycle_paths', _parse_multicycle_path),
    'set_clock_uncertainty': ('clock_attributes', _parse_clock_uncertainty),
    'set_timing_derate': ('timing_derate', _parse_timing_derate),
    'set_input_delay': ('io_delays', _parse_input_delay),
    'set_output_delay': ('io_delays', _parse_output_delay),
    'set_clock_groups': ('clock_groups', _parse_clock_groups),
    'set_case_analysis': ('case_analysis', _parse_generic),
    'set_disable_timing': ('disable_timing', _parse_generic),
    'set_ideal_network': ('ideal_network', _parse_generic),
    'set_max_delay': ('max_delay', _parse_generic),
    'set_min_delay': ('min_delay', _parse_generic),
    'set_operating_conditions': ('operating_conditions', _parse_generic),
    'set_clock_latency': ('clock_attributes', _parse_generic),
    'set_clock_transition': ('clock_attributes', _parse_generic),
    'set_clock_gating_check': ('clock_attributes', _parse_generic),
    'set_propagated_clock': ('clock_attributes', _parse_generic),
    'set_clock_jitter': ('clock_attributes', _parse_generic),
    'set_driving_cell': ('io_drive_load', _parse_generic),
    'set_input_transition': ('io_drive_load', _parse_generic),
    'set_load': ('io_drive_load', _parse_generic),
    'set_max_fanout': ('design_rules', _parse_generic),
    'set_max_transition': ('design_rules', _parse_generic),
    'set_max_capacitance': ('design_rules', _parse_generic),
    'set_max_area': ('design_rules', _parse_generic),
    'group_path': ('path_groups', _parse_generic),
    'set_max_dynamic_power': ('power', _parse_generic),
    'set_max_leakage_power': ('power', _parse_generic),
    'set_dont_use': ('dont_use', _parse_generic),
    'set_voltage': ('voltage', _parse_generic),
    'set_wire_load_mode': ('wire_load', _parse_generic),
    'set_wire_load_model': ('wire_load', _parse_generic),
}


# ── Parse SDC constraints ─────────────────────────────────────────────────────

def parse_sdc_constraints(
    text: str,
    symbol_table: Optional[SymbolTable] = None,
) -> List[Constraint]:
    """Parse SDC text into a list of Constraint objects.

    Supports variable resolution via SymbolTable.
    """
    text = _join_continuations(text)
    text = _strip_comments(text)

    if symbol_table:
        text = symbol_table.resolve(text)

    constraints: List[Constraint] = []
    for cmd, (category, parser) in _PARSERS.items():
        raw_cmds = _grab(text, rf'{re.escape(cmd)}[^;\n]*')
        for raw in raw_cmds:
            fields = parser(raw)
            constraints.append(Constraint(
                command_type=cmd,
                category=category,
                raw_text=raw.strip(),
                fields=fields,
                line_number=0,
            ))
    return constraints


# ── Constraint matching ───────────────────────────────────────────────────────

def _get_comparison_key(constraint: Constraint) -> str:
    """Generate a comparison key for matching constraints between versions."""
    fields = constraint.fields
    if constraint.command_type == 'create_clock':
        return f"clk:{fields.get('name', '')}"
    if constraint.command_type == 'create_generated_clock':
        return f"genclk:{fields.get('name', '')}"
    if constraint.command_type == 'set_false_path':
        return f"fp:{fields.get('from', '')}:{fields.get('to', '')}:{fields.get('through', '')}"
    if constraint.command_type == 'set_multicycle_path':
        return f"mcp:{fields.get('from', '')}:{fields.get('to', '')}"
    if constraint.command_type == 'set_clock_uncertainty':
        return f"unc:{fields.get('clocks', '')}"
    if constraint.command_type == 'set_timing_derate':
        return f"derate:{fields.get('timing_type', '')}:{fields.get('delay_type', '')}"
    return f"{constraint.command_type}:{constraint.raw_text[:60]}"


def _match_constraints(
    v1: List[Constraint],
    v2: List[Constraint],
) -> Tuple[List[Tuple[Constraint, Constraint]], List[Constraint], List[Constraint]]:
    """Match constraints between V1 and V2.

    Returns (matched_pairs, only_in_v1, only_in_v2).
    """
    v2_by_key: Dict[str, List[int]] = {}
    for idx, c in enumerate(v2):
        key = _get_comparison_key(c)
        v2_by_key.setdefault(key, []).append(idx)

    matched: List[Tuple[Constraint, Constraint]] = []
    only_in_v1: List[Constraint] = []
    used_v2: set = set()

    for c1 in v1:
        key = _get_comparison_key(c1)
        if key in v2_by_key:
            idx = v2_by_key[key].pop(0)
            if not v2_by_key[key]:
                del v2_by_key[key]
            used_v2.add(idx)
            matched.append((c1, v2[idx]))
        else:
            only_in_v1.append(c1)

    only_in_v2 = [c for idx, c in enumerate(v2) if idx not in used_v2]
    return matched, only_in_v1, only_in_v2


# ── Change rules ──────────────────────────────────────────────────────────────

_RULES = {
    "CHG-FP-001": ChangeRule("CHG-FP-001", "fatal",
        "A false path exception was removed — timing will now be checked on this path, likely causing violations."),
    "CHG-FP-002": ChangeRule("CHG-FP-002", "fatal",
        "A false path exception was narrowed — paths previously excluded are now timing-checked."),
    "CHG-FP-003": ChangeRule("CHG-FP-003", "info",
        "New false path exception added."),
    "CHG-MCP-001": ChangeRule("CHG-MCP-001", "fatal",
        "A multicycle path exception was removed — path reverts to single-cycle timing."),
    "CHG-MCP-002": ChangeRule("CHG-MCP-002", "fatal",
        "Multicycle setup cycles decreased — timing tightened, may cause setup violations."),
    "CHG-MCP-003": ChangeRule("CHG-MCP-003", "warning",
        "Multicycle setup cycles increased — looser timing, may hide real issues."),
    "CHG-MCP-004": ChangeRule("CHG-MCP-004", "fatal",
        "Setup multicycle exists but hold multicycle is missing — hold analysis will be wrong."),
    "CHG-CK-001": ChangeRule("CHG-CK-001", "warning",
        "Clock period decreased (higher frequency) — more demanding timing."),
    "CHG-CK-002": ChangeRule("CHG-CK-002", "warning",
        "Clock uncertainty decreased — less timing margin, tighter analysis."),
    "CHG-CK-003": ChangeRule("CHG-CK-003", "info",
        "Clock uncertainty increased — more margin, looser analysis."),
    "CHG-CK-004": ChangeRule("CHG-CK-004", "info",
        "Clock topology changed — clock added or removed."),
    "CHG-CK-005": ChangeRule("CHG-CK-005", "fatal",
        "Generated clock divide_by/multiply_by changed — output frequency changed, affects all downstream timing."),
    "CHG-DR-001": ChangeRule("CHG-DR-001", "warning",
        "Cell early derate reduced — less hold margin, may cause hold violations."),
    "CHG-DR-002": ChangeRule("CHG-DR-002", "warning",
        "Cell late derate increased — less setup margin, may cause setup violations."),
    "CHG-WC-001": ChangeRule("CHG-WC-001", "warning",
        "Wildcard pattern changed — may affect different objects than intended."),
    "CHG-WC-002": ChangeRule("CHG-WC-002", "warning",
        "Wildcard pattern broadened — may unintentionally cover more objects."),
    "CHG-IO-001": ChangeRule("CHG-IO-001", "warning",
        "Input/output delay value changed — I/O timing requirements altered."),
    "CHG-OC-001": ChangeRule("CHG-OC-001", "warning",
        "Operating conditions changed — different PVT corner."),
    "CHG-GEN-001": ChangeRule("CHG-GEN-001", "info",
        "New constraint added in V2."),
    "CHG-GEN-002": ChangeRule("CHG-GEN-002", "info",
        "Constraint removed in V2."),
    "CHG-GEN-003": ChangeRule("CHG-GEN-003", "info",
        "Non-critical field value changed."),
}


# ── Change classification ────────────────────────────────────────────────────

def _check_field_change(fields_a: Dict, fields_b: Dict, key: str) -> Optional[Tuple[Any, Any]]:
    """Return (old_val, new_val) if a specific field changed, else None."""
    val_a = fields_a.get(key)
    val_b = fields_b.get(key)
    if val_a != val_b:
        return (val_a, val_b)
    return None


def _is_mcp_hold_missing(constraints: List[Constraint]) -> bool:
    """Check if there are setup MCPs with no matching hold MCP."""
    setup_mcps = [c for c in constraints if c.command_type == 'set_multicycle_path' and 'setup' in c.fields]
    hold_mcps = [c for c in constraints if c.command_type == 'set_multicycle_path' and 'hold' in c.fields]
    # Check if any setup path lacks a matching hold path
    for s in setup_mcps:
        s_key = f"{s.fields.get('from', '')}:{s.fields.get('to', '')}"
        matched_hold = any(
            f"{h.fields.get('from', '')}:{h.fields.get('to', '')}" == s_key
            for h in hold_mcps
        )
        if not matched_hold and s.fields.get('setup', 1) > 1:
            return True
    return False


def classify_changes(
    matched: List[Tuple[Constraint, Constraint]],
    only_v1: List[Constraint],
    only_v2: List[Constraint],
) -> List[ConstraintChange]:
    """Apply change rules to matched/unmatched constraints.

    Returns a list of ConstraintChange objects with severity classification.
    """
    changes: List[ConstraintChange] = []

    # ── Removed constraints (in V1 but not V2) ─────────────────────────────
    for c in only_v1:
        cmd = c.command_type
        if cmd == 'set_false_path':
            changes.append(ConstraintChange(
                rule=_RULES["CHG-FP-001"],
                constraint_type=cmd,
                v1_text=c.raw_text, v2_text="",
                v1_fields=c.fields, v2_fields={},
                category=c.category, line_v1=c.line_number,
                explanation="False path removed — timing checker will now analyze this path.",
            ))
        elif cmd == 'set_multicycle_path':
            changes.append(ConstraintChange(
                rule=_RULES["CHG-MCP-001"],
                constraint_type=cmd,
                v1_text=c.raw_text, v2_text="",
                v1_fields=c.fields, v2_fields={},
                category=c.category, line_v1=c.line_number,
                explanation="Multicycle path removed — path reverts to single-cycle timing.",
            ))
        else:
            changes.append(ConstraintChange(
                rule=_RULES["CHG-GEN-002"],
                constraint_type=cmd,
                v1_text=c.raw_text, v2_text="",
                v1_fields=c.fields, v2_fields={},
                category=c.category, line_v1=c.line_number,
                explanation=f"Constraint removed in V2.",
            ))

    # ── Added constraints (in V2 but not V1) ───────────────────────────────
    for c in only_v2:
        cmd = c.command_type
        if cmd == 'set_false_path':
            changes.append(ConstraintChange(
                rule=_RULES["CHG-FP-003"],
                constraint_type=cmd,
                v1_text="", v2_text=c.raw_text,
                v1_fields={}, v2_fields=c.fields,
                category=c.category, line_v2=c.line_number,
                explanation="New false path exception added.",
            ))
        elif cmd == 'set_multicycle_path':
            changes.append(ConstraintChange(
                rule=_RULES["CHG-GEN-001"],
                constraint_type=cmd,
                v1_text="", v2_text=c.raw_text,
                v1_fields={}, v2_fields=c.fields,
                category=c.category, line_v2=c.line_number,
                explanation="New multicycle path added.",
            ))
        elif cmd == 'create_clock' or cmd == 'create_generated_clock':
            changes.append(ConstraintChange(
                rule=_RULES["CHG-CK-004"],
                constraint_type=cmd,
                v1_text="", v2_text=c.raw_text,
                v1_fields={}, v2_fields=c.fields,
                category=c.category, line_v2=c.line_number,
                explanation=f"New clock '{c.fields.get('name', '')}' added in V2.",
            ))
        else:
            changes.append(ConstraintChange(
                rule=_RULES["CHG-GEN-001"],
                constraint_type=cmd,
                v1_text="", v2_text=c.raw_text,
                v1_fields={}, v2_fields=c.fields,
                category=c.category, line_v2=c.line_number,
                explanation="New constraint added in V2.",
            ))

    # ── Modified constraints (in both, field values differ) ─────────────────
    for c1, c2 in matched:
        cmd = c1.command_type
        changed_fields = []
        all_keys = set(c1.fields.keys()) | set(c2.fields.keys())
        for k in all_keys:
            if c1.fields.get(k) != c2.fields.get(k):
                changed_fields.append((k, c1.fields.get(k), c2.fields.get(k)))

        if not changed_fields:
            continue

        # Apply specific rules per command type
        if cmd == 'set_false_path':
            # Check if from/to was narrowed (wildcard change)
            for key in ['from', 'to', 'through']:
                f_v1 = c1.fields.get(key, '')
                f_v2 = c2.fields.get(key, '')
                if f_v1 and f_v2 and f_v1 != f_v2:
                    wc = compare_wildcards(str(f_v1), str(f_v2), cmd)
                    if wc.change_type != "same":
                        changes.append(ConstraintChange(
                            rule=_RULES["CHG-WC-001"],
                            constraint_type=cmd,
                            v1_text=c1.raw_text, v2_text=c2.raw_text,
                            v1_fields=c1.fields, v2_fields=c2.fields,
                            category=c1.category,
                            explanation=f"False path {key} changed: {f_v1} -> {f_v2}. {wc.risk_explanation}",
                        ))
                    else:
                        changes.append(ConstraintChange(
                            rule=_RULES["CHG-FP-002"],
                            constraint_type=cmd,
                            v1_text=c1.raw_text, v2_text=c2.raw_text,
                            v1_fields=c1.fields, v2_fields=c2.fields,
                            category=c1.category,
                            explanation=f"False path parameters changed: {', '.join(f'{k}: {v1}->{v2}' for k, v1, v2 in changed_fields)}",
                        ))

        elif cmd == 'set_multicycle_path':
            # Check for setup cycle decrease
            setup_change = _check_field_change(c1.fields, c2.fields, 'setup')
            if setup_change:
                old_v, new_v = setup_change
                if isinstance(old_v, (int, float)) and isinstance(new_v, (int, float)):
                    if new_v < old_v:
                        changes.append(ConstraintChange(
                            rule=_RULES["CHG-MCP-002"],
                            constraint_type=cmd,
                            v1_text=c1.raw_text, v2_text=c2.raw_text,
                            v1_fields=c1.fields, v2_fields=c2.fields,
                            category=c1.category,
                            explanation=f"Setup cycles decreased from {old_v} to {new_v} — timing tightened significantly.",
                        ))
                    elif new_v > old_v:
                        changes.append(ConstraintChange(
                            rule=_RULES["CHG-MCP-003"],
                            constraint_type=cmd,
                            v1_text=c1.raw_text, v2_text=c2.raw_text,
                            v1_fields=c1.fields, v2_fields=c2.fields,
                            category=c1.category,
                            explanation=f"Setup cycles increased from {old_v} to {new_v} — timing loosened.",
                        ))
            # Check for missing hold - setup exists without matching hold
            hold_change = _check_field_change(c1.fields, c2.fields, 'hold')
            if hold_change:
                # hold was present in V1 but missing/zero in V2
                old_h, new_h = hold_change
                if old_h and old_h > 0 and not new_h:
                    changes.append(ConstraintChange(
                        rule=_RULES["CHG-MCP-004"],
                        constraint_type=cmd,
                        v1_text=c1.raw_text, v2_text=c2.raw_text,
                        v1_fields=c1.fields, v2_fields=c2.fields,
                        category=c1.category,
                        explanation="Hold multicycle removed — hold analysis will be incorrect.",
                    ))

        elif cmd == 'create_clock':
            period_change = _check_field_change(c1.fields, c2.fields, 'period')
            if period_change:
                old_p, new_p = period_change
                if isinstance(old_p, (int, float)) and isinstance(new_p, (int, float)):
                    if new_p < old_p:
                        changes.append(ConstraintChange(
                            rule=_RULES["CHG-CK-001"],
                            constraint_type=cmd,
                            v1_text=c1.raw_text, v2_text=c2.raw_text,
                            v1_fields=c1.fields, v2_fields=c2.fields,
                            category=c1.category,
                            explanation=f"Clock '{c1.fields.get('name', '')}' period decreased from {old_p}ns to {new_p}ns — {(1/new_p - 1/old_p)*1000:.1f}MHz frequency increase.",
                        ))
            name_change = _check_field_change(c1.fields, c2.fields, 'name')
            if name_change:
                changes.append(ConstraintChange(
                    rule=_RULES["CHG-CK-004"],
                    constraint_type=cmd,
                    v1_text=c1.raw_text, v2_text=c2.raw_text,
                    v1_fields=c1.fields, v2_fields=c2.fields,
                    category=c1.category,
                    explanation=f"Clock renamed: '{name_change[0]}' -> '{name_change[1]}'.",
                ))

        elif cmd == 'create_generated_clock':
            for key in ['divide_by', 'multiply_by']:
                chg = _check_field_change(c1.fields, c2.fields, key)
                if chg:
                    changes.append(ConstraintChange(
                        rule=_RULES["CHG-CK-005"],
                        constraint_type=cmd,
                        v1_text=c1.raw_text, v2_text=c2.raw_text,
                        v1_fields=c1.fields, v2_fields=c2.fields,
                        category=c1.category,
                        explanation=f"Generated clock '{c1.fields.get('name', '')}' {key} changed from {chg[0]} to {chg[1]}.",
                    ))

        elif cmd == 'set_clock_uncertainty':
            for key in ['setup_val', 'hold_val']:
                chg = _check_field_change(c1.fields, c2.fields, key)
                if chg:
                    old_v, new_v = chg
                    if isinstance(old_v, (int, float)) and isinstance(new_v, (int, float)):
                        if new_v < old_v:
                            changes.append(ConstraintChange(
                                rule=_RULES["CHG-CK-002"],
                                constraint_type=cmd,
                                v1_text=c1.raw_text, v2_text=c2.raw_text,
                                v1_fields=c1.fields, v2_fields=c2.fields,
                                category=c1.category,
                                explanation=f"Clock uncertainty {key.replace('_val', '')} decreased from {old_v}ns to {new_v}ns — {(old_v-new_v)/old_v*100:.0f}% margin reduction.",
                            ))
                        else:
                            changes.append(ConstraintChange(
                                rule=_RULES["CHG-CK-003"],
                                constraint_type=cmd,
                                v1_text=c1.raw_text, v2_text=c2.raw_text,
                                v1_fields=c1.fields, v2_fields=c2.fields,
                                category=c1.category,
                                explanation=f"Clock uncertainty {key.replace('_val', '')} increased from {old_v}ns to {new_v}ns.",
                            ))

        elif cmd == 'set_timing_derate':
            val_change = _check_field_change(c1.fields, c2.fields, 'value')
            if val_change:
                old_v, new_v = val_change
                timing_type = c1.fields.get('timing_type', '')
                delay_type = c1.fields.get('delay_type', '')
                if timing_type == 'early' and new_v < old_v:
                    changes.append(ConstraintChange(
                        rule=_RULES["CHG-DR-001"],
                        constraint_type=cmd,
                        v1_text=c1.raw_text, v2_text=c2.raw_text,
                        v1_fields=c1.fields, v2_fields=c2.fields,
                        category=c1.category,
                        explanation=f"Cell early derate decreased from {old_v} to {new_v} — less hold margin.",
                    ))
                elif timing_type == 'late' and new_v > old_v:
                    changes.append(ConstraintChange(
                        rule=_RULES["CHG-DR-002"],
                        constraint_type=cmd,
                        v1_text=c1.raw_text, v2_text=c2.raw_text,
                        v1_fields=c1.fields, v2_fields=c2.fields,
                        category=c1.category,
                        explanation=f"Cell late derate increased from {old_v} to {new_v} — less setup margin.",
                    ))

        elif cmd in ('set_input_delay', 'set_output_delay'):
            val_change = _check_field_change(c1.fields, c2.fields, 'value')
            if val_change:
                changes.append(ConstraintChange(
                    rule=_RULES["CHG-IO-001"],
                    constraint_type=cmd,
                    v1_text=c1.raw_text, v2_text=c2.raw_text,
                    v1_fields=c1.fields, v2_fields=c2.fields,
                    category=c1.category,
                    explanation=f"{cmd.replace('_', ' ')} value changed: {val_change[0]} -> {val_change[1]}.",
                ))

        elif cmd == 'set_operating_conditions':
            changes.append(ConstraintChange(
                rule=_RULES["CHG-OC-001"],
                constraint_type=cmd,
                v1_text=c1.raw_text, v2_text=c2.raw_text,
                v1_fields=c1.fields, v2_fields=c2.fields,
                category=c1.category,
                explanation=f"Operating conditions changed.",
            ))

        else:
            # Generic change
            changes.append(ConstraintChange(
                rule=_RULES["CHG-GEN-003"],
                constraint_type=cmd,
                v1_text=c1.raw_text, v2_text=c2.raw_text,
                v1_fields=c1.fields, v2_fields=c2.fields,
                category=c1.category,
                explanation=f"Field(s) changed: {', '.join(k for k, _, _ in changed_fields)}.",
            ))

    # ── Cross-cutting: check for MCP hold missing in both versions ────────
    # Only flag if this changed from V1 to V2 (was correct, now broken)
    all_v1 = [c for c, _ in matched] + only_v1
    all_v2 = [c for _, c in matched] + only_v2
    v1_missing_hold = _is_mcp_hold_missing(all_v1)
    v2_missing_hold = _is_mcp_hold_missing(all_v2)
    if not v1_missing_hold and v2_missing_hold:
        changes.append(ConstraintChange(
            rule=_RULES["CHG-MCP-004"],
            constraint_type="set_multicycle_path",
            v1_text="", v2_text="",
            v1_fields={}, v2_fields={},
            category="multicycle_paths",
            explanation="V2 has setup multicycle paths without matching hold constraints — introduced in new version.",
        ))

    # Deduplicate by rule + constraint key
    seen: set = set()
    unique_changes = []
    for c in changes:
        key = (c.rule.rule_id, c.v1_text[:60], c.v2_text[:60])
        if key not in seen:
            seen.add(key)
            unique_changes.append(c)

    return unique_changes


# ── Main entry point ──────────────────────────────────────────────────────────

def analyze_constraint_changes(
    sdc_v1: str,
    sdc_v2: str,
    linked_files_v1: Optional[Dict[str, str]] = None,
    linked_files_v2: Optional[Dict[str, str]] = None,
) -> ChangeAnalysisResult:
    """Compare two versions of an SDC file and report semantic changes.

    Args:
        sdc_v1: Text of V1 SDC file
        sdc_v2: Text of V2 SDC file
        linked_files_v1: {filename: content} for V1 linked TCL files
        linked_files_v2: {filename: content} for V2 linked TCL files

    Returns:
        ChangeAnalysisResult with changes, constraints, and statistics.
    """
    # Build symbol tables
    table_v1 = build_symbol_table(sdc_v1, linked_files_v1) if (linked_files_v1 or sdc_v1) else None
    table_v2 = build_symbol_table(sdc_v2, linked_files_v2) if (linked_files_v2 or sdc_v2) else None

    # Parse constraints
    cons_v1 = parse_sdc_constraints(sdc_v1, table_v1)
    cons_v2 = parse_sdc_constraints(sdc_v2, table_v2)

    # Match and classify
    matched, only_v1, only_v2 = _match_constraints(cons_v1, cons_v2)
    changes = classify_changes(matched, only_v1, only_v2)

    # Build statistics
    stats: Dict[str, int] = {
        "v1_constraints": len(cons_v1),
        "v2_constraints": len(cons_v2),
        "matched": len(matched),
        "added": len(only_v2),
        "removed": len(only_v1),
        "modified": sum(1 for c in changes if c.rule.severity in ("fatal", "warning") and c.v1_text and c.v2_text),
        "fatal": len([c for c in changes if c.rule.severity == "fatal"]),
        "warnings": len([c for c in changes if c.rule.severity == "warning"]),
        "info": len([c for c in changes if c.rule.severity == "info"]),
        "total_changes": len(changes),
    }

    return ChangeAnalysisResult(
        changes=changes,
        v1_constraints=cons_v1,
        v2_constraints=cons_v2,
        symbol_table_v1=table_v1,
        symbol_table_v2=table_v2,
        stats=stats,
    )
