# Feature 2: SDC Constraint Generator

> **Module:** `generator.py` · **CLI:** `sdc-tools generate` · **UI:** Generator Tab

---

## Why It's Needed

Writing SDC files from scratch is tedious and error-prone. Engineers commonly copy-paste from old projects, change a few values, and hope for the best — this leads to stale constraints, missing sections, and inconsistent formatting. The SDC Generator produces a complete, well-structured, synthesis-ready SDC file from structured parameters, eliminating boilerplate and ensuring every required section is present.

It's the fastest way to get from "I need constraints for my design" to a working SDC that passes the checker.

---

## How It Was Implemented

### Architecture

- **`SDCParams` dataclass** — flat configuration object with 40+ fields covering every SDC section
- **`generate_sdc(params)`** — pure function that builds the SDC line-by-line into a list, joins with `\n`, and returns a string
- **Composable sub-types** — `ClockDef`, `FalsePath`, `MultiCyclePath`, `HalfCyclePath`, `CaseAnalysisEntry`, `DisableArc`, `PathGroup` — each with defaults
- **All sections generated** — header, clocks, clock attributes, I/O, design rules, operating conditions, derate, ideal networks, DFT, timing exceptions, power, dont-use

### Generated SDC Sections

| Section | Lines | Controlled By |
|---------|-------|---------------|
| File header + version | 3 | `design_name`, `sdc_version` |
| Units | 1 | `add_units`, `time_unit`, `cap_unit` |
| Clock definitions | ~2/clk | `clocks[]` — primary, generated, virtual |
| Clock attributes | ~3/clk | uncertainty, latency, propagated, transition, jitter |
| CDC groups | ~3/Nclk | Auto-generated if >1 primary clock |
| I/O constraints | ~8 | `in_delay_*`, `out_delay_*`, `drive_cell`, `load` |
| Design rules | ~5 | `max_fanout`, `max_transition`, `max_cap` |
| Operating conditions | 1 | `add_oper_cond`, `oper_cond_name` |
| Timing derate | 4 | `add_derate`, `derate_*` |
| Ideal/DFT | ~4 | `add_ideal_rst`, `add_scan` |
| Case analysis | ~1/entry | `case_entries[]` |
| Disable arcs | ~1/arc | `disable_arcs[]` |
| Path groups | ~N | `path_groups[]` |
| False paths | ~1/path | `false_paths[]` |
| Multicycle paths | ~2/path | `mc_paths[]` (hold auto-added) |
| Half-cycle paths | ~2/path | `half_paths[]` |
| Power constraints | 2 | `add_power`, `max_dyn_power`, `max_leak_power` |
| Dont-use cells | ~1/cell | `dont_use[]` |

---

## Use Cases

| Scenario | Why |
|----------|-----|
| **New design kickoff** | Generate baseline constraints in seconds |
| **Design exploration** | Rapidly iterate clock frequencies and derate values |
| **Teaching / learning SDC** | See how SDC sections relate to design parameters |
| **Test generation** | Create known-good SDC files for tool testing |
| **Template standardization** | Teams get consistent SDC output every time |

---

## Structural View

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   SDCParams  │────▶│  generate_sdc()  │────▶│  SDC text string│
│  (dataclass) │     │                  │     │  (ready to use) │
└──────────────┘     │  1. Build header │     └─────────────────┘
                     │  2. Emit clocks  │
                     │  3. Emit I/O     │
                     │  4. Emit rules   │
                     │  5. Emit derate  │
                     │  6. Emit excepts │
                     │  7. Emit power   │
                     └──────────────────┘
```

## Flow Diagram

```
SDCParams instance
      │
      ▼
┌──────────────────────────────────────────┐
│  generate_sdc()                          │
│                                          │
│  L = []                                  │
│                                          │
│  # Phase 1: Header                       │
│  L.append("set sdc_version 2.2")         │
│  L.append("set_units -time ns ...")      │
│                                          │
│  # Phase 2: Clock definitions            │
│  for clk in clocks:                      │
│      if primary: create_clock ...        │
│      if virtual:  create_clock (no port) │
│      if generated: create_generated_clk  │
│                                          │
│  # Phase 3: Clock attributes             │
│  for clk in clocks:                      │
│      set_clock_uncertainty -setup/hold   │
│  if latency:    set_clock_latency ...    │
│  if propagated: set_propagated_clock ... │
│  if transition: set_clock_transition ... │
│  if jitter:     set_clock_jitter ...     │
│  if gating:     set_clock_gating_check   │
│                                          │
│  # Phase 4: I/O constraints              │
│  set_input_delay -max/-min               │
│  set_output_delay -max/-min              │
│  set_driving_cell / set_input_transition │
│  set_load                                │
│                                          │
│  # Phase 5: Design rule constraints      │
│  set_max_fanout / set_max_transition     │
│  set_max_capacitance / set_max_area      │
│                                          │
│  # Phase 6: Operating conditions         │
│  set_operating_conditions -max WORST     │
│                                          │
│  # Phase 7: Timing derate                │
│  set_timing_derate -late/early cell/net  │
│                                          │
│  # Phase 8: Ideal networks & DFT         │
│  set_ideal_network (reset + scan)        │
│  set_case_analysis (scan mode)           │
│  set_min_pulse_width                     │
│  set_case_analysis entries               │
│  set_disable_timing arcs                 │
│                                          │
│  # Phase 9: Timing exceptions            │
│  set_false_path pairs                    │
│  set_multicycle_path setup/hold pairs    │
│  Half-cycle paths (rise↔fall)            │
│  group_path directives                   │
│                                          │
│  # Phase 10: Power & dont-use            │
│  set_max_dynamic_power                   │
│  set_max_leakage_power                   │
│  set_dont_use cell list                  │
│                                          │
│  return "\n".join(L)                     │
└──────────────────────────────────────────┘
      │
      ▼
  Complete SDC text
```

---

## CLI Usage

```bash
# Minimal — single clock
sdc-tools generate --design MY_CHIP --clock clk=10.0 > my_chip.sdc

# Multiple clocks with port
sdc-tools generate \
  --design MY_CHIP \
  --clock clk_core=5.0:sys_clk \
  --clock clk_slow=20.0:slow_clk \
  --uncertainty 0.12 \
  --operating-condition WORST \
  --derate \
  --propagated \
  --output my_chip.sdc

# With DFT and reset handling
sdc-tools generate \
  --design MY_CHIP \
  --clock clk=10.0:clk \
  --ideal-reset --reset-port rst_n \
  --scan --scan-port scan_en \
  --operating-condition SSG_0P72V_M40C \
  --derate
```

## Python API

```python
from generator import SDCParams, ClockDef, FalsePath, generate_sdc

params = SDCParams(
    design_name="MY_CHIP",
    clocks=[
        ClockDef(name="clk_core", port="sys_clk", period=5.0, uncertainty=0.15),
        ClockDef(name="clk_slow", port="slow_clk", period=20.0, uncertainty=0.3),
    ],
    in_delay_max=1.2,
    out_delay_max=1.5,
    max_fanout=20,
    add_oper_cond=True,
    oper_cond_name="WORST",
    add_derate=True,
    false_paths=[FalsePath(from_obj="rst_n", to_obj="FF_OUT/D")],
)

sdc_text = generate_sdc(params)
print(sdc_text)
```

## Integration with Live SDC Validation

The Generator tab in the Streamlit UI automatically runs the checker on the generated SDC output, showing live validation results:
- **Errors** → must fix before using in synthesis
- **Warnings** → review before tapeout
- **Info** → best practice suggestions

This creates a tight **edit → generate → validate** feedback loop.

---

*Part of SDC Tools — an open-source VLSI constraint development toolkit.*