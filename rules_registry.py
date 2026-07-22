"""
Rules Registry — Centralized documentation for all checker/warning codes.

Every SDC-NNN and CHG-XXX-NNN code used across the project is defined here
with descriptions, engineering context, fix suggestions, and external references.
Modules (checker.py, mmc.py, etc.) still use their own inline code strings;
this module is the single documentation source for the UI reference table.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional

APP_VERSION = "1.2.0"


@dataclass
class Rule:
    """One check/rule definition."""
    code: str           # "SDC-001", "CHG-FP-001"
    severity: str       # "error" | "warning" | "info" | "fatal"
    short_name: str     # short label, e.g. "Missing Clock Definition"
    description: str    # what the check detects
    why_matters: str    # real engineering impact
    fix: str            # how to fix it
    reference_url: str  # external docs (empty string if none)
    module: str         # which module produces this code
    added_version: str  # when this rule was introduced


# ── All rules ──────────────────────────────────────────────────────────────────

RULES: Dict[str, Rule] = {}

def _r(code, severity, name, desc, why, fix, url, module, ver="1.0.0"):
    RULES[code] = Rule(code, severity, name, desc, why, fix, url, module, ver)

# ── Checker ERRORS (SDC-001..011) ─────────────────────────────────────────────

_r("SDC-001", "error", "Missing Clock Definition",
   "No create_clock defined in the SDC file.",
   "Without a clock, the synthesis tool has no timing reference — all paths are unconstrained and QoR is meaningless.",
   "Add 'create_clock -name clk -period <ns> [get_ports <port>]' for every clock domain.",
   "https://www.synopsys.com/glossary/what-is-sdc.html", "checker")

_r("SDC-002", "error", "Duplicate Clock Name",
   "Two or more create_clock commands share the same -name value.",
   "Duplicate names cause the tool to silently overwrite the first clock definition, leading to wrong timing.",
   "Use unique names for each clock domain, or use -add if multiple clocks on the same port.",
   "", "checker")

_r("SDC-003", "error", "Generated Clock Missing -source",
   "A create_generated_clock command is missing the required -source flag.",
   "Without -source the tool cannot determine the master clock edge, producing random divider behavior.",
   "Add '-source [get_ports <port>]' or '-source [get_pins <pin>]' to the create_generated_clock.",
   "", "checker")

_r("SDC-004", "error", "Conflicting Divide/Multiply",
   "A create_generated_clock has both -divide_by and -multiply_by set.",
   "These flags are mutually exclusive — using both produces undefined frequency.",
   "Use either -divide_by OR -multiply_by, not both.",
   "", "checker")

_r("SDC-005", "error", "No Input Delay",
   "Clocks are defined but no set_input_delay exists.",
   "All input ports are timing-unconstrained — setup/hold at input boundaries is never checked.",
   "Add 'set_input_delay -max <value> [get_ports <port>]' for each input port.",
   "https://www.synopsys.com/glossary/what-is-sdc.html", "checker")

_r("SDC-006", "error", "No Output Delay",
   "Clocks are defined but no set_output_delay exists.",
   "All output ports are timing-unconstrained — the tool cannot verify output timing.",
   "Add 'set_output_delay -max <value> [get_ports <port>]' for each output port.",
   "https://www.synopsys.com/glossary/what-is-sdc.html", "checker")

_r("SDC-007", "error", "Clock on Data Port",
   "A create_clock is defined on a port whose name suggests it is a data bus (data, addr, bus, wdata, etc.).",
   "Creating a clock on a data port constrains data as a clock, which breaks timing analysis.",
   "Use a dedicated clock port. If this is a data strobe, use set_clock_latency or set_input_delay instead.",
   "", "checker")

_r("SDC-008", "error", "Input Delay >= Clock Period",
   "A set_input_delay value is greater than or equal to the clock period.",
   "This leaves zero or negative time for combinational logic — timing closure is mathematically impossible.",
   "Reduce input delay or increase clock period. Check if the delay value is in the correct unit (ns vs ps).",
   "", "checker")

_r("SDC-009", "error", "Output Delay >= Clock Period",
   "A set_output_delay value is greater than or equal to the clock period.",
   "Zero margin for output logic means the path can never meet timing.",
   "Reduce output delay or increase clock period.",
   "", "checker")

_r("SDC-010", "error", "Propagated Clock on Virtual Clock",
   "set_propagated_clock is applied to a virtual clock (no source port).",
   "Virtual clocks have no physical source — there is nothing to propagate through the network.",
   "Remove set_propagated_clock for virtual clocks, or convert the virtual clock to a real clock with a source port.",
   "", "checker")

_r("SDC-011", "error", "Invalid Case Analysis Value",
   "set_case_analysis has a value other than 0, 1, rising, or falling.",
   "The tool only recognizes these four values — anything else causes a parse error or silent ignore.",
   "Use 'set_case_analysis 0', 'set_case_analysis 1', 'set_case_analysis rising', or 'set_case_analysis falling'.",
   "", "checker")

# ── Checker WARNINGS (SDC-020..045) ───────────────────────────────────────────

_r("SDC-020", "warning", "Suspicious False Path",
   "A set_false_path -from X -to Y does not contain typical async/scan/test keywords.",
   "False paths bypass timing analysis — an incorrect false path hides real violations.",
   "Verify the path is genuinely false (async CDC, test mode, etc.). Add a comment explaining why.",
   "", "checker")

_r("SDC-021", "warning", "Multicycle Without Hold Fix",
   "A multicycle -setup N path is missing the corresponding -hold (N-1) adjustment.",
   "Without the hold fix, the tool checks hold at the original 1-cycle boundary — causing false hold violations.",
   "Add '-hold <N-1>' to match every '-setup N' multicycle path.",
   "https://www.synopsys.com/glossary/what-is-sdc.html", "checker")

_r("SDC-022", "warning", "Unrealistically Tight Uncertainty",
   "Clock uncertainty is set below 0.05ns.",
   "Overly tight uncertainty causes the tool to over-optimize, producing designs that fail in silicon.",
   "Use a realistic uncertainty value based on PLL jitter + clock tree skew (typically 0.1-0.3ns).",
   "", "checker")

_r("SDC-023", "warning", "Very High Clock Uncertainty",
   "Clock uncertainty is set above 0.5ns.",
   "High uncertainty wastes timing margin — the tool adds unnecessary buffer insertion, hurting area and power.",
   "Verify the uncertainty value. For most designs, 0.1-0.3ns is appropriate.",
   "", "checker")

_r("SDC-024", "warning", "Multiple Clocks Without Clock Groups",
   "Multiple clocks defined but no set_clock_groups command found.",
   "Without clock group declarations, the tool analyzes all cross-clock paths as synchronous — missing real CDC issues.",
   "Add 'set_clock_groups -asynchronous -group [get_clocks X] -group [get_clocks Y]' for unrelated clock domains.",
   "https://www.ausdia.com/blog/5/seemingly-simple-clock-relations-quiz/filter/0", "checker")

_r("SDC-025", "warning", "Wildcard dont_touch",
   "set_dont_touch is applied with a wildcard ([all_cells] or *).",
   "This blocks ALL optimization, severely degrading QoR (area, timing, power).",
   "Apply dont_touch only to specific cells/nets that need it, not globally.",
   "", "checker")

_r("SDC-026", "warning", "Extremely Tight max_transition",
   "set_max_transition is below 0.05ns.",
   "Ultra-tight transition constraints cause excessive buffer insertion and may be physically unachievable.",
   "Use a realistic transition target (typically 0.1-0.3ns depending on technology node).",
   "", "checker")

_r("SDC-027", "warning", "set_max_delay Without -datapath_only",
   "A set_max_delay constraint is missing -datapath_only.",
   "Without this flag, the constraint also affects hold analysis on the same path, potentially causing incorrect results.",
   "Add '-datapath_only' unless you intentionally want to constrain both setup and hold.",
   "", "checker")

_r("SDC-028", "warning", "No Input Delay -min",
   "set_input_delay exists but no -min variant.",
   "Hold timing at input ports cannot be checked without -min input delay.",
   "Add 'set_input_delay -min <value> [get_ports <port>]' for hold analysis.",
   "", "checker")

_r("SDC-029", "warning", "No Output Delay -min",
   "set_output_delay exists but no -min variant.",
   "Hold timing at output ports is unconstrained.",
   "Add 'set_output_delay -min <value> [get_ports <port>]' for hold analysis.",
   "", "checker")

_r("SDC-030", "warning", "No set_propagated_clock",
   "Clocks are defined but set_propagated_clock is missing.",
   "The ideal clock model assumes zero insertion delay and skew — overly optimistic for post-layout correlation.",
   "Add 'set_propagated_clock [all_clocks]' after CTS to model real clock tree delay.",
   "", "checker")

_r("SDC-031", "warning", "Clock Groups Missing Exclusion Type",
   "A set_clock_groups command is missing -asynchronous, -logically_exclusive, or -physically_exclusive.",
   "Without an exclusion type, the constraint has no effect — cross-clock paths are still analyzed as synchronous.",
   "Add the appropriate flag: -asynchronous (no phase relation), -physically_exclusive (same port), or -logically_exclusive (mux-select).",
   "https://www.ausdia.com/blog/5/seemingly-simple-clock-relations-quiz/filter/0", "checker")

_r("SDC-032", "warning", "Derate Early Without Late",
   "set_timing_derate has -early but no matching -late.",
   "Unbalanced derate skews setup vs hold analysis in opposite directions, producing inconsistent results.",
   "Add a matching -late derate value.",
   "", "checker")

_r("SDC-033", "warning", "Derate Late Without Early",
   "set_timing_derate has -late but no matching -early.",
   "Same issue as SDC-032 — asymmetric derate.",
   "Add a matching -early derate value.",
   "", "checker")

_r("SDC-034", "warning", "Data Check Without -clock",
   "set_data_check is missing a -clock reference.",
   "Without -clock, the tool cannot determine which edge to check against.",
   "Add '-clock [get_clocks <name>]' to the set_data_check command.",
   "", "checker")

_r("SDC-035", "warning", "Excessive Disable Timing",
   "More than 5 set_disable_timing commands found.",
   "Large numbers of disable_timing arcs can hide real timing violations by disabling critical paths.",
   "Review each disable_timing — ensure they are necessary and not masking real issues.",
   "", "checker")

_r("SDC-036", "warning", "Disable Timing Without From/To",
   "A set_disable_timing command is missing both -from and -to.",
   "This disables ALL timing arcs on the specified cell — almost always wrong and hides real violations.",
   "Add explicit -from and -to pin specifiers to disable only the intended arc.",
   "", "checker")

_r("SDC-037", "warning", "Half-Cycle Without Hold Fix",
   "Half-cycle multicycle paths (-rise_to/-fall_to on -setup) found without matching -hold 0.",
   "Hold analysis will be wrong at the half-cycle boundary.",
   "Add '-hold 0' with matching -rise_to/-fall_to for each half-cycle setup path.",
   "", "checker")

_r("SDC-040", "warning", "cell_early Derate < 1.0",
   "set_timing_derate -early -cell_delay is below 1.0.",
   "Early derate < 1.0 makes cells faster, reducing hold margin — opposite of intended conservative analysis.",
   "Use cell_early > 1.0 (e.g., 1.05) for conservative hold analysis.",
   "https://www.synopsys.com/glossary/what-is-aocv.html", "checker")

_r("SDC-041", "warning", "cell_late Derate > 1.0",
   "set_timing_derate -late -cell_delay is above 1.0.",
   "Late derate > 1.0 makes cells faster, reducing setup margin — should be < 1.0 for conservative analysis.",
   "Use cell_late < 1.0 (e.g., 0.95) for conservative setup analysis.",
   "https://www.synopsys.com/glossary/what-is-aocv.html", "checker")

_r("SDC-042", "warning", "net_early Derate < 1.0",
   "set_timing_derate -early -net_delay is below 1.0.",
   "Early net derate < 1.0 reduces hold margin on interconnect delays.",
   "Use net_early > 1.0 for conservative hold analysis.",
   "https://www.synopsys.com/glossary/what-is-aocv.html", "checker")

_r("SDC-043", "warning", "net_late Derate > 1.0",
   "set_timing_derate -late -net_delay is above 1.0.",
   "Late net derate > 1.0 reduces setup margin on interconnect delays.",
   "Use net_late < 1.0 for conservative setup analysis.",
   "https://www.synopsys.com/glossary/what-is-aocv.html", "checker")

_r("SDC-044", "warning", "Unrecognized Operating Condition",
   "set_operating_conditions name doesn't match common patterns (WORST, BEST, TYP, SSG, TT, FFG, etc.).",
   "Non-standard names may indicate a typo or missing library setup.",
   "Verify the condition name matches your library's operating condition definitions.",
   "", "checker")

_r("SDC-045", "warning", "Hold/Setup Uncertainty Ratio",
   "Clock uncertainty -hold is not approximately 0.5x of -setup.",
   "Hold uncertainty should typically be ~half of setup uncertainty (skew dominates hold). Unusual ratios may indicate a typo.",
   "Review the values — typically -hold ≈ 0.5 * -setup.",
   "", "checker")

# ── MMC checks (SDC-050..054) ─────────────────────────────────────────────────

_r("SDC-050", "warning", "Clock Mismatch Across Corners",
   "Clock names or definitions differ between PVT corners.",
   "Inconsistent clock definitions cause wrong timing analysis in some corners.",
   "Ensure all corners have matching clock definitions.",
   "https://www.ausdia.com/blog/7/taming-mmmc-mayhem/filter/0", "mmc")

_r("SDC-051", "info", "Clock Period Differs Between Corners",
   "Clock periods differ across corners (may be intentional for multi-mode).",
   "This is often intentional (e.g., different modes at different frequencies) but should be verified.",
   "Confirm the period differences are intentional multi-mode design.",
   "", "mmc")

_r("SDC-053", "warning", "Missing Timing Exceptions in Some Corners",
   "A timing exception (false path, multicycle, etc.) exists in some corners but is missing in others.",
   "Missing exceptions cause the tool to analyze paths that should be excluded, producing false violations.",
   "Add the missing timing exceptions to all relevant corners.",
   "", "mmc")

_r("SDC-054", "warning", "Derate Not Monotonically Ordered",
   "Derate values are not monotonically ordered across PVT corners (e.g., worst has lower derate than typical).",
   "Non-monotonic derate violates the corner ordering assumption — results from different corners cannot be compared.",
   "Verify derate ordering: worst-case should be most conservative (highest cell_early, lowest cell_late).",
   "https://www.ausdia.com/blog/7/taming-mmmc-mayhem/filter/0", "mmc")

# ── Clock relations (SDC-060..063) ────────────────────────────────────────────

_r("SDC-060", "warning", "Async Instead of Physically Exclusive",
   "Clock pair marked -asynchronous but should be -physically_exclusive (same source port, different periods).",
   "-asynchronous causes unnecessary Crosstalk/SI analysis on paths that can never physically exist simultaneously.",
   "Change to 'set_clock_groups -physically_exclusive' for clocks sharing the same source port.",
   "https://www.ausdia.com/blog/5/seemingly-simple-clock-relations-quiz/filter/0", "clock_relations", "1.2.0")

_r("SDC-061", "warning", "Exclusive But Clocks Are Synchronous",
   "Clock pair marked -logically_exclusive or -physically_exclusive but clocks have a real timing relationship (parent-child/synchronous).",
   "This masks real setup/hold timing paths, leaving them un-optimized — can cause silicon failure.",
   "Remove the set_clock_groups for synchronous clocks (parent-child or same-master relationships don't need exclusion).",
   "https://www.ausdia.com/blog/5/seemingly-simple-clock-relations-quiz/filter/0", "clock_relations", "1.2.0")

_r("SDC-062", "info", "Missing Clock Relationship",
   "An asynchronous or physically exclusive clock pair has no set_clock_groups entry.",
   "Without explicit grouping, the tool may analyze cross-domain paths as synchronous (over-constraining).",
   "Add 'set_clock_groups -asynchronous -group [get_clocks X] -group [get_clocks Y]'.",
   "", "clock_relations", "1.2.0")

_r("SDC-063", "info", "Wrong Exclusion Type",
   "Clock pair marked with an exclusion type (-logically_exclusive or -physically_exclusive) but appears to be asynchronous.",
   "Using exclusion instead of -asynchronous may be overly restrictive or indicate a design intent mismatch.",
   "Verify the exclusion type is intentional. Use -asynchronous for unrelated clock domains.",
   "", "clock_relations", "1.2.0")

# ── Best practices / INFO (SDC-100..140) ──────────────────────────────────────

_r("SDC-100", "info", "Missing sdc_version",
   "No 'set sdc_version' declaration found.",
   "Tool version compatibility may be affected without an explicit version declaration.",
   "Add 'set sdc_version 2.2' at the top of the SDC file.",
   "", "checker")

_r("SDC-101", "info", "Missing set_units",
   "No set_units declaration found.",
   "Without explicit units, different tools may interpret numeric values differently (ns vs ps).",
   "Add 'set_units -time ns -capacitance pF'.",
   "", "checker")

_r("SDC-102", "info", "Missing set_max_fanout",
   "No set_max_fanout constraint.",
   "Unconstrained fanout can create high-capacity nets that slow down transitions.",
   "Add 'set_max_fanout 20 [all_inputs]' (adjust for your technology).",
   "", "checker")

_r("SDC-103", "info", "Missing set_max_transition",
   "No set_max_transition constraint.",
   "Unconstrained slew can cause signal integrity issues and increased dynamic power.",
   "Add 'set_max_transition 0.2 [all_nets]' (adjust for your technology).",
   "", "checker")

_r("SDC-104", "info", "Missing set_max_capacitance",
   "No set_max_capacitance constraint.",
   "Unconstrained capacitance affects signal integrity and power.",
   "Add 'set_max_capacitance 0.5 [all_nets]' (adjust for your technology).",
   "", "checker")

_r("SDC-105", "info", "Missing set_load",
   "No set_load on output ports.",
   "Without output load, the tool optimizes for zero fanout — unrealistic for real interconnect.",
   "Add 'set_load 0.05 [get_ports <output>]' based on expected board trace capacitance.",
   "", "checker")

_r("SDC-106", "info", "Missing Driving Cell / Input Transition",
   "No set_driving_cell, set_input_transition, or set_drive on input ports.",
   "Ideal input slew is overly optimistic — real drivers have finite output impedance.",
   "Add 'set_driving_cell -cell <cell> [all_inputs]' or 'set_input_transition 0.1 [all_inputs]'.",
   "", "checker")

_r("SDC-107", "info", "Missing Clock Latency",
   "No set_clock_latency defined.",
   "Without source latency, the tool assumes the clock arrives at the chip boundary with zero delay.",
   "Add 'set_clock_latency -source <value> [all_clocks]' for off-chip clock insertion delay.",
   "", "checker")

_r("SDC-108", "info", "Missing Clock Transition",
   "No set_clock_transition defined.",
   "Ideal clock transition (zero slew) is unrealistic and affects clock gating check accuracy.",
   "Add 'set_clock_transition 0.1 [all_clocks]' based on PLL output characteristics.",
   "", "checker")

_r("SDC-109", "info", "Missing set_case_analysis",
   "No set_case_analysis for DFT/test signals.",
   "Without case_analysis, DFT paths (scan_en, test_mode) dominate timing analysis.",
   "Add 'set_case_analysis 0 [get_ports scan_en]' (or 1) to fix DFT signal values.",
   "", "checker")

_r("SDC-110", "info", "Missing set_ideal_network",
   "No set_ideal_network to mark reset/scan as ideal.",
   "Reset and scan signals modeled as real nets waste optimization effort on non-functional paths.",
   "Add 'set_ideal_network [get_nets rst_n scan_en]' for pre-CTS reset/scan networks.",
   "", "checker")

_r("SDC-111", "info", "Excessive False Paths",
   "More than 10 set_false_path commands found.",
   "Large numbers of false paths may indicate overly broad exclusions that hide real violations.",
   "Audit each false path to ensure it is genuinely false. Consider using set_clock_groups instead.",
   "", "checker")

_r("SDC-112", "info", "Excessive Multicycle Paths",
   "More than 8 set_multicycle_path commands found.",
   "Many multicycle paths suggest complex timing protocols — each one needs documentation.",
   "Document each multicycle path with a comment explaining the data protocol.",
   "", "checker")

_r("SDC-113", "info", "Missing set_dont_use",
   "No set_dont_use constraint.",
   "Without dont_use, the tool may use weak or problematic cells (e.g., low-Vt, clock buffers on data paths).",
   "Add 'set_dont_use [get_lib_cells <lib>/dont_use_cell]' to exclude problematic cells.",
   "", "checker")

_r("SDC-114", "info", "Missing Operating Conditions",
   "No set_operating_conditions defined.",
   "Without explicit PVT corner, the tool uses library defaults — may not match target corner.",
   "Add 'set_operating_conditions -max <corner_name>' for the target PVT.",
   "", "checker")

_r("SDC-115", "info", "Missing set_timing_derate",
   "No set_timing_derate defined.",
   "Without derate, the tool uses nominal delays — insufficient for AOCV/POCVM advanced signoff.",
   "Add set_timing_derate values for cell and net early/late delays.",
   "", "checker")

_r("SDC-116", "info", "Missing set_clock_jitter",
   "No set_clock_jitter defined.",
   "Random jitter is not modeled separately from uncertainty — may over/under-constrain.",
   "Add 'set_clock_jitter <value> [get_clocks <name>]' based on PLL specifications.",
   "", "checker")

_r("SDC-117", "info", "Missing group_path",
   "No group_path defined.",
   "Without path grouping, synthesis optimizes all paths equally — critical interfaces may not get priority.",
   "Add 'group_path -name <name> -from <start> -to <end> -weight <N>' for critical paths.",
   "", "checker")

_r("SDC-118", "info", "Missing set_clock_gating_check",
   "No set_clock_gating_check defined.",
   "If the design uses clock gating cells, the tool won't check setup/hold on gating pin without this.",
   "Add 'set_clock_gating_check -setup 0.0 -hold 0.0 [all_clocks]' or target specific gating cells.",
   "", "checker")

_r("SDC-119", "info", "Disable Timing Present",
   "set_disable_timing commands found in the SDC.",
   "Disable_timing arcs hide timing paths — verify each is intentional and not masking real violations.",
   "Review each set_disable_timing with -from/-to pin specificity.",
   "", "checker")

_r("SDC-120", "info", "set_min_delay Present",
   "set_min_delay constraints found.",
   "min_delay can conflict with hold constraints — verify no overlap.",
   "Check that set_min_delay and set_multicycle_path -hold don't target the same paths.",
   "", "checker")

_r("SDC-121", "info", "Missing Wire Load Constraints",
   "No set_wire_load_mode or set_wire_load_model defined.",
   "Without wire load, interconnect delay is estimated with default models — may not match physical layout.",
   "Add wire load constraints for pre-layout synthesis, or remove if using wireload-free flow.",
   "", "checker")

_r("SDC-122", "info", "Missing set_max_area",
   "No set_max_area constraint.",
   "Without area target, synthesis optimizes only timing — may produce oversized designs.",
   "Add 'set_max_area <value>' to constrain total cell area.",
   "", "checker")

_r("SDC-123", "info", "Missing Power Constraints",
   "No set_max_dynamic_power or set_max_leakage_power defined.",
   "Without power constraints, synthesis ignores power optimization.",
   "Add 'set_max_dynamic_power <value>' and/or 'set_max_leakage_power <value>' for power-aware synthesis.",
   "", "checker")

_r("SDC-124", "info", "Clock Gating Without Min Pulse Width",
   "set_clock_gating_check is present but no set_min_pulse_width.",
   "Narrow pulses may trigger clock gating cells incorrectly — min_pulse_width prevents glitches.",
   "Add 'set_min_pulse_width <value> [get_clocks <name>]' to prevent narrow-pulse triggering.",
   "", "checker")

_r("SDC-125", "info", "Voltage Without Voltage Area",
   "set_voltage found but no create_voltage_area.",
   "set_voltage without a voltage area has no effect — the voltage domain is undefined.",
   "Add 'create_voltage_area -region <name> [get_ports <port>]' to define the voltage domain.",
   "", "checker")

_r("SDC-126", "info", "Virtual Clocks Detected",
   "Virtual clocks (no source port) are defined.",
   "Virtual clocks model off-chip interfaces — ensure I/O delay constraints reference them correctly.",
   "Verify set_input_delay/set_output_delay uses -clock [get_clocks <virtual_clk>].",
   "", "checker")

_r("SDC-130", "info", "Operating Conditions Without Corner Context",
   "set_operating_conditions found but no corner/mode comments in the file.",
   "Without comments, it's unclear which PVT corner this SDC targets.",
   "Add comments like '# Corner: WORST, SS/0.9V/125C' near the set_operating_conditions.",
   "", "checker")

_r("SDC-131", "info", "Multiple Operating Conditions",
   "Multiple set_operating_conditions commands found in one file.",
   "Multiple conditions in one file may indicate a copy-paste error or incorrect multi-corner setup.",
   "Each SDC file should typically have one set_operating_conditions for its target corner.",
   "", "checker")

_r("SDC-132", "info", "Derate Without Operating Conditions",
   "set_timing_derate found but no set_operating_conditions.",
   "Derate values are corner-specific — without operating conditions, the corner context is unclear.",
   "Add set_operating_conditions or a comment identifying the target corner.",
   "", "checker")

_r("SDC-140", "info", "Clock Relation Analysis Skipped",
   "The clock relation analyzer failed to run (likely an import or parse error).",
   "Clock relation checks (SDC-060..063) were not performed — potential issues may be missed.",
   "Check that clock_relations.py is importable and the SDC text is valid.",
   "", "checker", "1.2.0")

# ── Constraint change rules (CHG-*) ───────────────────────────────────────────

_r("CHG-FP-001", "fatal", "False Path Removed",
   "A set_false_path from V1 was removed in V2.",
   "Removed false paths cause the tool to analyze previously-excluded paths — often leading to timing violations.",
   "Restore the false path or verify the path is truly no longer false.",
   "https://www.ausdia.com", "constraint_diff", "1.1.0")

_r("CHG-FP-002", "fatal", "False Path Target Changed",
   "A set_false_path -from/-to/-through changed between V1 and V2.",
   "Changed false path targets may leave real paths un-excluded while excluding different paths.",
   "Verify both the old and new false path targets are correct.",
   "", "constraint_diff", "1.1.0")

_r("CHG-FP-003", "info", "False Path Added",
   "A new set_false_path appeared in V2.",
   "New false paths reduce timing analysis coverage — verify the path is genuinely false.",
   "Review the new false path to ensure it doesn't mask real violations.",
   "", "constraint_diff", "1.1.0")

_r("CHG-MCP-001", "fatal", "Multicycle Setup Decreased",
   "A multicycle -setup N was changed to a smaller value.",
   "Reduced setup cycles tighten timing — paths that previously met timing may now fail.",
   "Verify the new multicycle value is correct for the data protocol.",
   "", "constraint_diff", "1.1.0")

_r("CHG-MCP-002", "fatal", "Multicycle Hold Decreased",
   "A multicycle -hold N was changed to a smaller value.",
   "Reduced hold cycles tighten hold analysis — may cause false hold violations.",
   "Verify the hold multicycle matches the setup multicycle (hold = setup - 1).",
   "", "constraint_diff", "1.1.0")

_r("CHG-MCP-003", "warning", "Multicycle Increased",
   "A multicycle path cycles count was increased.",
   "More relaxed multicycle — previously analyzed paths may no longer be checked at the correct boundary.",
   "Verify the increase is intentional and matches the data protocol.",
   "", "constraint_diff", "1.1.0")

_r("CHG-MCP-004", "fatal", "Multicycle Removed",
   "A set_multicycle_path from V1 was removed in V2.",
   "Removed multicycle paths revert to single-cycle analysis — paths that needed multi-cycle will now fail.",
   "Restore the multicycle path or verify the protocol changed.",
   "", "constraint_diff", "1.1.0")

_r("CHG-CK-001", "warning", "Clock Period Decreased",
   "A clock period was reduced (frequency increased).",
   "Higher frequency tightens all timing paths — may cause setup violations.",
   "Verify the new frequency is achievable for the design.",
   "", "constraint_diff", "1.1.0")

_r("CHG-CK-002", "warning", "Clock Period Increased",
   "A clock period was increased (frequency decreased).",
   "Lower frequency relaxes timing — paths previously analyzed at higher frequency may have excess margin.",
   "Verify the frequency reduction is intentional.",
   "", "constraint_diff", "1.1.0")

_r("CHG-CK-003", "info", "Clock Added",
   "A new create_clock appeared in V2.",
   "New clocks add timing domains — may require new CDC constraints.",
   "Add corresponding set_clock_groups, I/O delays, and uncertainty for the new clock.",
   "", "constraint_diff", "1.1.0")

_r("CHG-CK-004", "info", "Clock Removed",
   "A create_clock from V1 was removed in V2.",
   "Removed clocks eliminate a timing domain — associated constraints become orphaned.",
   "Remove or update any constraints that reference the deleted clock.",
   "", "constraint_diff", "1.1.0")

_r("CHG-CK-005", "fatal", "Clock Port Changed",
   "A create_clock source port changed between V1 and V2.",
   "Changing the clock port means the clock is now on a different physical pin — all I/O delays and CDC constraints may be wrong.",
   "Verify the new port is correct and update all related constraints.",
   "", "constraint_diff", "1.1.0")

_r("CHG-DR-001", "warning", "Derate Value Changed",
   "A set_timing_derate value changed between V1 and V2.",
   "Changed derate values alter timing margins across the design — may cause or hide violations.",
   "Verify the new derate is appropriate for the target corner.",
   "", "constraint_diff", "1.1.0")

_r("CHG-DR-002", "warning", "Derate Direction Changed",
   "A derate shifted from -early to -late or vice versa.",
   "Swapping derate direction completely reverses the timing impact — setup becomes hold and vice versa.",
   "Verify the direction is correct for the intended analysis.",
   "", "constraint_diff", "1.1.0")

_r("CHG-WC-001", "warning", "Wildcard Pattern Changed",
   "A wildcard object filter (get_cells, get_pins, etc.) changed between V1 and V2.",
   "Changed wildcards may narrow or broaden the set of affected objects, altering which paths are constrained.",
   "Verify the new pattern matches the intended object set.",
   "", "constraint_diff", "1.1.0")

_r("CHG-WC-002", "warning", "Wildcard Narrowed",
   "A wildcard pattern now matches fewer objects than in V1.",
   "Narrowed wildcards leave some previously-constrained objects unconstrained.",
   "Ensure the narrowed pattern still covers all intended objects.",
   "", "constraint_diff", "1.1.0")

_r("CHG-IO-001", "warning", "I/O Delay Changed",
   "A set_input_delay or set_output_delay value changed.",
   "Changed I/O delays alter timing margins at port boundaries.",
   "Verify the new delay matches the interface specification.",
   "", "constraint_diff", "1.1.0")

_r("CHG-OC-001", "warning", "Operating Condition Changed",
   "set_operating_conditions changed between V1 and V2.",
   "Different operating conditions mean a different PVT corner — all derate and uncertainty values should be reviewed.",
   "Ensure the new condition matches the intended corner and all related values are updated.",
   "", "constraint_diff", "1.1.0")

_r("CHG-GEN-001", "info", "New Constraint Added",
   "A new SDC constraint appeared in V2 that wasn't in V1.",
   "New constraints add timing restrictions that weren't previously checked.",
   "Review the new constraint to ensure it's correct and necessary.",
   "", "constraint_diff", "1.1.0")

_r("CHG-GEN-002", "info", "Constraint Removed",
   "An SDC constraint from V1 was removed in V2.",
   "Removed constraints relax timing analysis — paths previously constrained may now be unconstrained.",
   "Verify the removal is intentional and doesn't leave timing gaps.",
   "", "constraint_diff", "1.1.0")

_r("CHG-GEN-003", "info", "Constraint Modified",
   "An SDC constraint text changed between V1 and V2 (not covered by specific rules above).",
   "Review the modification to ensure it's correct.",
   "Compare V1 and V2 text to understand the change.",
   "", "constraint_diff", "1.1.0")


# ── Lookup helpers ─────────────────────────────────────────────────────────────

def get_all_rules() -> List[Rule]:
    """Return all rules sorted by code."""
    return sorted(RULES.values(), key=lambda r: r.code)


def get_rules_by_module(module: str) -> List[Rule]:
    """Return rules for a specific module."""
    return [r for r in RULES.values() if r.module == module]


def get_rule(code: str) -> Optional[Rule]:
    """Look up a single rule by code."""
    return RULES.get(code)


def get_rules_by_severity(severity: str) -> List[Rule]:
    """Return rules matching a severity level."""
    return [r for r in RULES.values() if r.severity == severity]
