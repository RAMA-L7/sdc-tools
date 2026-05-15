# SDC Tools

> A web-based constraint toolkit for VLSI synthesis engineers — validate, debug, and generate `.sdc` files from a clean browser UI. No EDA tool required.

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35%2B-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Live Demo](https://img.shields.io/badge/Live%20Demo-Streamlit%20Cloud-FF4B4B?logo=streamlit&logoColor=white)](https://sdc-tools-8mxtuhwy5myvejdcmpuwbp.streamlit.app/)
[![Part of VLSI Hub](https://img.shields.io/badge/Part%20of-VLSI%20Hub-0f172a)](https://github.com/RAMA-L7/vlsi-hub)

---

## Overview

Writing and debugging SDC constraint files is error-prone and time-consuming. **SDC Tools** provides two utilities in a single Streamlit app:

| Tool | What it does |
|------|-------------|
| **Checker / Validator** | Parses your `.sdc` file and reports errors, warnings, and best-practice suggestions with code references |
| **SDC Generator** | Builds a complete, synthesis-ready `.sdc` from a structured form — with live preview and one-click download |

Supports all standard SDC commands across primary clocks, generated clocks, virtual clocks, I/O constraints, timing exceptions, DFT, AOCV derate, power, and more.

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

**Best practices** — 26 suggestions including missing `set_units`, `set_clock_transition`, `set_timing_derate`, `group_path`, `set_operating_conditions`, power constraints, and more.

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

---

## Project Structure

```
sdc-tools/
│
├── app.py              # Streamlit UI — Checker and Generator tabs
├── checker.py          # SDC parser and validation logic (pure Python, no deps)
├── generator.py        # SDC constraint generation logic (pure Python, no deps)
├── requirements.txt    # Only requires: streamlit
│
└── samples/
    └── example.sdc     # Sample SDC file to test the checker
```

`checker.py` and `generator.py` are pure Python with no external dependencies — they can be imported and used directly in any Python script or FastAPI backend.

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

---

## License

MIT © [RAMA-L7](https://github.com/RAMA-L7)
