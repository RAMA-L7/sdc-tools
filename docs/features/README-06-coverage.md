# Feature 6: Constraint Coverage Gap Analysis

> **Module:** `coverage.py` · **CLI:** `sdc-tools coverage`, `sdc-tools report coverage` · **UI:** Coverage Tab

---

## Why It's Needed

When reviewing an SDC file, the question isn't just _"what's wrong?"_ — it's also _"what's missing?"_ A constraint coverage gap analysis measures _which categories of constraints are present vs. absent_. This is the same gap analysis that Ausdia TimeVision provides: a quick visual assessment of signoff readiness.

For example, an SDC might have all clocks defined but be missing AOCV derate entirely — that's a critical gap for advanced-node signoff. The Coverage Analyzer gives a single percentage score across 39 items in 6 categories, highlighting exactly what's missing and how critical each gap is.

---

## How It Was Implemented

### Data Model

- **`CoverageItem`** — one constraint item (name, cmd, present flag, detail string, is_critical)
- **`CoverageCategory`** — group of related items (name, icon, items[], computed total/covered/missing/score/status)
- **`CoverageResult`** — full analysis (filename, categories[], totals, score, stats)

### 6 Categories, 39 Items

| Category | Icon | Items | Critical Items |
|----------|------|-------|----------------|
| **Clocks** | 🕐 | 9 | create_clock, uncertainty, propagated, clock groups (if >1) |
| **I/O Constraints** | 🔌 | 6 | input/output delay max+min |
| **Timing Exceptions** | ⚠️ | 7 | multicycle hold fix (if mc paths exist) |
| **Design Rules** | 📏 | 6 | max_fanout, max_transition |
| **AOCV / Derate** | 📊 | 5 | timing_derate, operating_conditions |
| **Power / DFT** | ⚡ | 6 | (none critical by default) |

Each item has an `is_critical` flag — missing critical items are marked with `*` in the UI.

### Score Calculation

```
score = total_present / total_items × 100

≥ 80% → "good"   (green)
≥ 50% → "warn"   (amber)
< 50% → "bad"    (red)
```

---

## Use Cases

| Scenario | Why |
|----------|-----|
| **Signoff readiness check** | One number tells you if your SDC is complete |
| **Gap analysis** | See exactly which constraint categories are under-defined |
| **Tool migration** | Compare coverage when moving between EDA vendor tools |
| **Audit / review** | Checklist-grade verification of constraint completeness |
| **SDC maturity tracking** | Track coverage % across design milestones |

---

## Structural View

```
┌──────────────┐     ┌────────────────────────┐     ┌──────────────────┐
│  SDC Text    │────▶│  parse_sdc_coverage()  │────▶│  CoverageResult  │
│              │     │                        │     │                  │
│              │     │  1. Parse 30+ commands │     │  filename         │
│              │     │     via regex          │     │  categories[]     │
│              │     │  2. Build 6 categories │     │  total_items      │
│              │     │     with 39 items      │     │  total_present    │
│              │     │  3. Mark present/      │     │  total_missing    │
│              │     │     missing per item   │     │  score (%)        │
│              │     │  4. Compute scores     │     │  stats{}          │
│              │     │                        │     └──────────────────┘
│              │     │  CoverageCategory:     │
│              │     │  ┌────────────────┐    │
│              │     │  │ name, icon     │    │
│              │     │  │ items[]        │    │
│              │     │  │ total, covered │    │
│              │     │  │ missing, score │    │
│              │     │  │ status (g/w/b) │    │
│              │     │  └────────────────┘    │
│              │     │                        │
│              │     │  CoverageItem:          │
│              │     │  ┌────────────────┐    │
│              │     │  │ name, cmd      │    │
│              │     │  │ present (bool) │    │
│              │     │  │ detail (str)   │    │
│              │     │  │ is_critical    │    │
│              │     │  └────────────────┘    │
│              │     └────────────────────────┘
└──────────────┘
```

## Flow Diagram

```
SDC Text Input
      │
      ▼
┌────────────────────────────────────────────┐
│  Parse 30+ command patterns via _grab()    │
│  • Count occurrences of each command       │
│  • Extract specific flags (-min, -early)   │
└────────────────────────────────────────────┘
      │
      ▼
┌────────────────────────────────────────────┐
│  Category 1: Clocks (9 items)             │
│  ┌─────────────────────────────────────┐   │
│  │ create_clock: count > 0?            │   │
│  │ create_generated_clock: count > 0?  │   │
│  │ set_clock_latency: count > 0?      │   │
│  │ set_clock_transition: count > 0?   │   │
│  │ set_clock_uncertainty: count > 0?  │   │
│  │ set_clock_jitter: count > 0?       │   │
│  │ set_propagated_clock: count > 0?   │   │
│  │ set_clock_groups: count > 0?       │   │
│  │ set_clock_gating_check: count > 0? │   │
│  └─────────────────────────────────────┘   │
└────────────────────────────────────────────┘
      │
      ▼
┌────────────────────────────────────────────┐
│  Category 2: I/O Constraints (6 items)    │
│  set_input_delay, -min variant            │
│  set_output_delay, -min variant           │
│  set_driving_cell / input_transition      │
│  set_load                                  │
└────────────────────────────────────────────┘
      │
      ▼
┌────────────────────────────────────────────┐
│  Category 3: Timing Exceptions (7 items)  │
│  set_false_path, set_multicycle_path       │
│  MCP hold fix, set_max_delay              │
│  set_min_delay, group_path,               │
│  set_disable_timing                        │
└────────────────────────────────────────────┘
      │
      ▼
┌────────────────────────────────────────────┐
│  Category 4: Design Rules (6 items)       │
│  sdc_version, set_units, max_fanout       │
│  max_transition, max_capacitance          │
│  max_area                                  │
└────────────────────────────────────────────┘
      │
      ▼
┌────────────────────────────────────────────┐
│  Category 5: AOCV / Derate (5 items)      │
│  set_timing_derate, early+late pairs       │
│  cell+net derate, operating_conditions    │
│  wire_load_mode                            │
└────────────────────────────────────────────┘
      │
      ▼
┌────────────────────────────────────────────┐
│  Category 6: Power / DFT (6 items)        │
│  max_dynamic_power, max_leakage_power     │
│  set_case_analysis, set_dont_use           │
│  set_ideal_network, set_min_pulse_width   │
└────────────────────────────────────────────┘
      │
      ▼
┌────────────────────────────────────────────┐
│  Compute totals and score                  │
│  total_items = ∑cat.total                 │
│  total_present = ∑cat.covered             │
│  score = present / items × 100            │
│                                            │
│  ≥ 80% → "good" (green)                   │
│  ≥ 50% → "warn" (amber)                   │
│  < 50% → "bad" (red)                      │
└────────────────────────────────────────────┘
```

---

## CLI Usage

```bash
# Full coverage analysis
sdc-tools coverage design.sdc

# JSON output
sdc-tools coverage design.sdc --json

# Show only missing items (compact)
sdc-tools coverage design.sdc --missing-only

# Generate HTML coverage report
sdc-tools report coverage design.sdc --output coverage_report.html

# Save text output
sdc-tools coverage design.sdc --output coverage.txt
```

## Python API

```python
from coverage import parse_sdc_coverage

with open("design.sdc") as f:
    text = f.read()

result = parse_sdc_coverage(text, "design.sdc")

print(f"Overall score: {result.score:.1f}%")
print(f"  {result.total_present}/{result.total_items} items present")
print(f"  {result.total_missing} missing")

for cat in result.categories:
    print(f"\n{cat.icon} {cat.name}: {cat.score:.0f}% ({cat.covered}/{cat.total})")
    for item in cat.items:
        status = "✓" if item.present else "✗"
        crit = " *" if item.is_critical and not item.present else ""
        print(f"  [{status}] {item.name}{crit}")
        if item.detail:
            print(f"       {item.detail}")

# Access critical missing items
for cat in result.categories:
    for item in cat.items:
        if not item.present and item.is_critical:
            print(f"CRITICAL: [{cat.name}] {item.name} — {item.detail}")
```

## UI: Coverage Tab

The Streamlit UI shows:
- **Large score percentage** (color-coded: green/amber/red)
- **4 summary metrics** — coverage %, present count, missing count, categories
- **Per-category expanders** — each with progress bar + item table
- **Missing items summary** — critical items highlighted in red
- **Download HTML report** button

---

*Part of SDC Tools — an open-source VLSI constraint development toolkit.*