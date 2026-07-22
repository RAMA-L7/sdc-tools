# SDC Tools

> A web-based constraint toolkit for VLSI synthesis engineers — validate, debug, generate, and manage multi-corner SDC files from a clean browser UI. No EDA tool required.

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35%2B-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Live Demo](https://img.shields.io/badge/Live%20Demo-Streamlit%20Cloud-FF4B4B?logo=streamlit&logoColor=white)](https://sdc-tools-8mxtuhwy5myvejdcmpuwbp.streamlit.app/)
[![Part of VLSI Hub](https://img.shields.io/badge/Part%20of-VLSI%20Hub-0f172a)](https://github.com/RAMA-L7/vlsi-hub)

---

## Overview

Writing and debugging SDC constraint files is error-prone and time-consuming. **SDC Tools** provides six utilities in a single Streamlit app:

| Tool | What it does |
|------|-------------|
| **🛡 Checker / Validator** | Parses your `.sdc` file and reports errors, warnings, and best-practice suggestions with code references |
| **⚙️ SDC Generator** | Builds a complete, synthesis-ready `.sdc` from a structured form — with live validation, quick multi-corner generation, and baseline comparison |
| **🔲 MMC Corner Manager** | Define and manage PVT timing corners with presets, validation, import/export, and coverage matrix |
| **📦 MMC SDC Generator** | Generate per-corner SDCs from a base template, diff corners, cross-corner consistency checks, and ZIP download |
| **🔍 Constraint Change Analyzer** | Detect hidden changes between two SDC versions — resolves TCL variables, identifies wildcard drift, and flags timing-impacting changes |
| **🕐 Clock Relations** | Analyze all clock pairs in an SDC, infer correct relationships, and detect mismatches in `set_clock_groups` constraints |

Supports all standard SDC commands across primary clocks, generated clocks, virtual clocks, I/O constraints, timing exceptions, DFT, AOCV derate, power, and more.

Inspired by [Ausdia's "Taming MMC Mayhem"](https://www.ausdia.com/blog/7/taming-mmmc-mayhem/filter/0) — the MMC features address the challenge of managing dozens of PVT corners in modern SoC signoff flows.

---

## 🚀 Live Demo

**Try it now — no install needed:**

> **[https://sdc-tools-8mxtuhwy5myvejdcmpuwbp.streamlit.app/](https://sdc-tools-8mxtuhwy5myvejdcmpuwbp.streamlit.app/)**

Hosted on Streamlit Cloud. Upload your own `.sdc` file or use the built-in sample to test the checker instantly.

---

## Features

### 🛡 Checker / Validator

Analyzes any `.sdc` or `.tcl` file and reports findings across three severity levels:

**Errors** — issues that will cause incorrect synthesis or tool failures
- Missing `create_clock` — no timing reference defined
- No `set_input_delay` / `set_output_delay` — unconstrained ports
- `create_generated_clock` missing required `-source`
- `set_propagated_clock` applied to a virtual clock
- Input or output delay greater than or equal to the clock period
- Invalid `set_case_analysis` value
- Duplicate clock names

**Warnings** — issues that produce wrong results silently
- Multicycle path without a `-hold` counterpart
- Multiple clocks without `set_clock_groups` (CDC risk)
- Half-cycle paths without matching `-hold 0`
- `set_max_delay` without `-datapath_only`
- Missing `-min` delays for hold analysis
- No `set_propagated_clock` (over-optimistic ideal clock model)
- `set_disable_timing` without `-from`/`-to` pins
- Unbalanced `set_timing_derate` early/late pairs
- MMC-aware derate reasonableness checks (SDC-040..043)
- Clock uncertainty hold/setup ratio validation (SDC-045)

**Best practices** — 30+ suggestions including missing `set_units`, `set_clock_transition`, `set_timing_derate`, `group_path`, `set_operating_conditions`, power constraints, corner context, and more.

---

### ⚙️ SDC Generator

Form-based generator with live SDC preview. Covers every major constraint category:

**Clocks**
- Primary clocks — name, port, period, duty cycle, uncertainty (hold auto = ½ setup)
- Generated clocks — full switch set: `-divide_by`, `-multiply_by`, `-duty_cycle`, `-edge_shift`, `-invert`, `-preinvert`, `-combinational`, `-add`, `-master_clock`
- Virtual clocks — no source port, for I/O interface modeling
- Clock attributes — latency, `set_propagated_clock`, transition, jitter, gating check
- CDC auto-detection — `set_clock_groups -asynchronous` generated when multiple primary clocks exist

**I/O Constraints**
- `-max` and `-min` input/output delays for setup and hold
- `set_driving_cell` or `set_input_transition` (mutually exclusive)
- `set_load` on outputs

**Design Rules**
- `set_max_fanout`, `set_max_transition`, `set_max_capacitance`, `set_min_capacitance`, `set_max_area`

**Advanced**
- Operating conditions — PVT corner specification
- Timing derate — AOCV with separate early/late cell and net factors
- Ideal networks — reset port false path + ideal network
- DFT / Scan — `set_case_analysis` with `0 / 1 / rising / falling`, multiple entries, port or pin scope
- Disable timing arcs — per arc with explicit `-from`/`-to` pins
- Path groups — `group_path` with from/to/weight
- Wire load — mode and model for legacy flows
- False paths, multicycle paths (hold auto-added), half-cycle paths (`-rise_to` / `-fall_to`)
- Power — `set_max_dynamic_power`, `set_max_leakage_power`
- Dont-use cells

**Inline Features (after generation)**

- **Live SDC Validation** — automatically runs the full checker on the generated SDC, showing errors, warnings, and info inline
- **Quick Multi-Corner Generate** — if corners are defined, generate per-corner SDCs directly from the generator tab with cross-corner consistency checks, corner diff view, and ZIP download
- **Compare Against Baseline** — upload an existing SDC to compare against the newly generated version using semantic constraint change analysis (TCL variable resolution, wildcard drift, timing-impacting changes)

---

### 🔲 MMC Corner Manager

Define and manage PVT timing corners for multi-corner SDC generation:

- **Corner presets** — Classic 3-corner (Worst/Typ/Best), Industrial 5-corner, Full 8-corner signoff, or Custom
- **Per-corner parameters** — name, process type, voltage, temperature, operating condition, derate values (cell/net early/late), uncertainty scale
- **Validation** — voltage range (0.3–1.5V), temperature (-55–175°C), derate bounds (0.5–1.5), process type recognition
- **Import/Export** — save corner definitions as JSON, import from file
- **Coverage matrix** — visual summary table of all corners and their attributes

---

### 📦 MMC SDC Generator

Generate per-corner SDC files from a single base template:

- **Base template** — configure clocks, I/O delays, design rules, DFT once
- **Per-corner generation** — each corner gets its own SDC with corner-specific `set_operating_conditions`, `set_timing_derate`, and scaled clock uncertainty
- **Corner diff view** — side-by-side comparison highlighting differences (green = added, red = removed, yellow = changed)
- **Cross-corner consistency checks** — validates clock definitions, timing exceptions, and derate ordering across corners (SDC-050..054)
- **ZIP download** — bundle all corner SDCs into a single ZIP file
- **Individual download** — download any single corner SDC

---

### 🔍 Constraint Change Analyzer

Detect hidden changes between two SDC versions that would go unnoticed in a text diff:

- **TCL variable resolution** — resolves `$VARNAME` references by parsing linked TCL files, detecting value changes that standard diffs miss
- **Constraint parsing** — extracts structured objects from each SDC command (clocks, false paths, multicycle paths, uncertainty, derate, I/O delays)
- **Semantic diff** — matches constraints between V1 and V2 by type and target, identifies added, removed, and modified constraints
- **Severity classification** — flags changes as **Fatal** (causes violations), **Warning** (reduced margin), or **Info** (notable change)
- **Wildcard pattern analysis** — detects when object filters change scope (narrowed/broadened/rewritten)
- **Change impact rules** — 20+ rules modeled on Ausdia TimeVision:
  - Removed false path → Fatal
  - Multicycle cycles decreased → Fatal
  - Clock uncertainty decreased → Warning
  - Wildcard pattern changed → Warning
  - New constraint added → Info
- **Variable resolution view** — shows what each variable resolved to in V1 vs V2
- **Side-by-side text diff** — traditional text diff alongside semantic analysis

| Change Rule | Severity | Description |
|-------------|----------|-------------|
| CHG-FP-001 | Fatal | False path removed — timing now checked |
| CHG-MCP-002 | Fatal | Multicycle setup cycles decreased |
| CHG-CK-001 | Warning | Clock period decreased (higher freq) |
| CHG-WC-001 | Warning | Wildcard pattern changed |
| CHG-IO-001 | Warning | I/O delay value changed |
| CHG-GEN-001 | Info | New constraint added |

| Code | Severity | Description |
|------|----------|-------------|
| SDC-040 | Warning | `cell_early` derate < 1.0 (typically > 1.0) |
| SDC-041 | Warning | `cell_late` derate > 1.0 (typically < 1.0) |
| SDC-042 | Warning | `net_early` derate < 1.0 (typically > 1.0) |
| SDC-043 | Warning | `net_late` derate > 1.0 (typically < 1.0) |
| SDC-044 | Warning | Operating condition name doesn't match common patterns |
| SDC-045 | Warning | Clock uncertainty hold is not ~0.5× of setup |
| SDC-130 | Info | Operating conditions without corner context in comments |
| SDC-131 | Info | Multiple `set_operating_conditions` in one file |
| SDC-132 | Info | Derate values without operating conditions |
| SDC-050 | Warning | Clock definitions differ between corners |
| SDC-051 | Info | Clock periods differ between corners (may be multi-mode) |
| SDC-053 | Warning | Timing exceptions present in some corners but missing in others |
| SDC-060 | Warning | Clock pair marked `-asynchronous` but should be `-physically_exclusive` (same port, different period) |
| SDC-061 | Warning | Clock pair marked `-logically_exclusive` but clocks have real timing paths (parent-child/synchronous) |
| SDC-062 | Info | Clock pair has no relationship specified (missing `set_clock_groups` entry) |
| SDC-063 | Info | Clock pair marked with wrong exclusion type (verify intentional) |

---

### 🕐 Clock Relations

Analyzes clock relationships in SDC files to detect incorrect or missing `set_clock_groups` constraints:

- **Clock parsing** — extracts all `create_clock` and `create_generated_clock` definitions with period, source port, and master clock
- **Relation inference** — determines the correct relationship for every clock pair using rules from the SDC clock relation quiz:
  - **Physically exclusive** — same source port, different periods (only one active at a time)
  - **Synchronous** — parent-child (generated from master) or siblings from same master
  - **Asynchronous** — different source ports, no common master
- **Mismatch detection** — flags incorrect `-asynchronous` (should be `-physically_exclusive`) and incorrect `-logically_exclusive` (masks real timing paths)
- **Clock relation matrix** — color-coded N×N table showing correct/mismatched/missing relationships with hover tooltips
- **Checker integration** — SDC-060..063 rules in the checker tab automatically validate clock groups

**Inspired by:** [Ausdia's Seemingly Simple Clock Relations Quiz](https://www.ausdia.com/blog/5/seemingly-simple-clock-relations-quiz/filter/0)

---

### 📋 Rules Registry

A centralized documentation system for all 95 checker rule codes across the project:

- **Searchable reference table** — look up any `SDC-NNN` or `CHG-XXX-NNN` code by number, keyword, or module
- **Engineering context** — each rule includes "why it matters" and "how to fix" descriptions
- **External references** — links to Ausdia blog posts, Synopsys documentation, and SDC specification
- **Version tracking** — `added_version` field tracks when each rule was introduced
- **Module filtering** — filter rules by source module (checker, mmc, clock_relations, constraint_diff)
- **Severity filtering** — filter by error, warning, info, or fatal

Accessible via the "📋 Rule Reference" expander at the bottom of the Checker tab. The sidebar shows the current version with a changelog of what's new.

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/RAMA-L7/sdc-tools.git
cd sdc-tools

# 2. Install dependencies (only streamlit required)
pip install -r requirements.txt

# 3. Launch the app
streamlit run app.py
```

The app opens automatically at **`http://localhost:8501`**

> **Python 3.11** is recommended (used in the live deployment).

---

## Testing Locally

**Run the checker from the terminal** (no browser needed):

```bash
python -c "
from checker import check_sdc
result = check_sdc(open('samples/example.sdc').read())
print(f'Errors:   {len(result.errors)}')
print(f'Warnings: {len(result.warnings)}')
print(f'Info:     {len(result.info)}')
for i in result.errors:   print(f'  [ERROR]   {i.code}: {i.msg}')
for i in result.warnings: print(f'  [WARNING] {i.code}: {i.msg}')
"
```

**Run the generator from the terminal:**

```bash
python -c "
from generator import SDCParams, generate_sdc
sdc = generate_sdc(SDCParams(design_name='MY_CHIP'))
print(sdc)
"
```

**Test multi-corner generation from the terminal:**

```bash
python -c "
from corner_manager import CORNER_PRESETS
from generator import SDCParams, ClockDef
from mmc import generate_corner_sdcs, create_corner_zip

corners = CORNER_PRESETS['Classic 3-corner (Worst/Typ/Best)']
template = SDCParams(
    design_name='MY_CHIP',
    clocks=[ClockDef(name='clk_core', port='clk', period=5.0, uncertainty=0.15)],
    add_ideal_rst=True, rst_port='rst_n',
)
sdcs = generate_corner_sdcs(template, corners)
for name, text in sdcs.items():
    print(f'{name}: {text.count(chr(10))+1} lines')
"
```

---

## Project Structure

```
sdc-tools/
│
├── app.py              # Streamlit UI — 6 tabs + rule reference
├── checker.py          # SDC parser and validation logic (pure Python, no deps)
├── generator.py        # SDC constraint generation logic (pure Python, no deps)
├── corner_manager.py   # MMC corner data model, presets, validation, serialization
├── mmc.py              # Multi-corner operations: generation, diff, cross-corner checks, ZIP
├── tcl_resolver.py     # TCL variable parsing and resolution
├── wildcard_analyzer.py# Wildcard pattern analysis and comparison
├── constraint_diff.py  # Constraint change impact analysis (semantic diff + rules)
├── clock_relations.py  # Clock relation analysis and mismatch detection
├── rules_registry.py   # Centralized rule code documentation + lookup + versioning
├── requirements.txt    # Only requires: streamlit
│
└── samples/
    ├── example.sdc              # Sample SDC file to test the checker
    ├── constraint_diff_v1.sdc   # V1 for constraint change analyzer
    ├── constraint_diff_v2.sdc   # V2 (identical commands, variables differ)
    ├── variables_v1.tcl         # V1 linked variable definitions
    ├── variables_v2.tcl         # V2 linked variable definitions
    └── clock_relations.sdc      # Blog post quiz example (5 clocks, 4 clock groups)
```

All logic modules (`checker.py`, `generator.py`, `corner_manager.py`, `mmc.py`, `tcl_resolver.py`, `wildcard_analyzer.py`, `constraint_diff.py`, `clock_relations.py`, `rules_registry.py`) are pure Python with no external dependencies — they can be imported and used directly in any Python script or FastAPI backend.

---

## Integration with VLSI Hub

SDC Tools is a standalone project and also a module within [VLSI Hub](https://github.com/RAMA-L7/vlsi-hub) — an open-source EDA intelligence platform for synthesis engineers.

The same checker and generator logic powers the `SDCToolsPage` component in the VLSI Hub React frontend.

---

## Contributing

Contributions are welcome. To add a new check:

1. Open `checker.py`
2. Add your regex pattern in the `check_sdc()` function
3. Append an `Issue` (error/warning) or `InfoItem` to the result
4. Use the next available `SDC-NNN` code

To add a new generator field:

1. Add the parameter to `SDCParams` in `generator.py`
2. Add the UI widget in `app.py` under the relevant expander
3. Wire the widget value into the `SDCParams` constructor at the bottom of the generator tab

To add a new constraint change rule:

1. Add the rule to `_RULES` dict in `constraint_diff.py` with an ID like `CHG-XXX-NNN`
2. Add the detection logic in `classify_changes()` matching on the relevant `command_type`
3. Follow the existing pattern: compare `v1_fields` vs `v2_fields`, create a `ConstraintChange` with the rule

---

## License

MIT © [RAMA-L7](https://github.com/RAMA-L7)
