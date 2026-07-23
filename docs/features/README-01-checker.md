# Feature 1: SDC Constraint Checker / Validator

> **Module:** `checker.py` · **CLI:** `sdc-tools check` · **UI:** Checker Tab · **Code:** SDC-001..043, SDC-060..063, SDC-100..132

---

## Why It's Needed

SDC (Synopsys Design Constraints) files are hand-written or script-generated text files that tell synthesis tools how to optimize a digital design. A single mistake — a missing clock, a duplicated name, an unrealistically tight uncertainty — can produce silicon that fails timing, wastes power, or doesn't function. Engineers spend hours debugging constraint bugs that could be caught in seconds.

The SDC Checker automates this review: it parses the SDC, runs 40+ semantic checks, and reports errors (_must fix_), warnings (_should review_), and info tips (_best practices_). It's the **first line of defense** before running synthesis.

---

## How It Was Implemented

### Architecture

- **Single-pass parser** — reads the SDC text once using regex, extracting all 30+ SDC command types
- **Rule-based checker** — 40+ individual `if` conditions, each producing an `Issue(code, severity, message)` or `InfoItem(code, message)`
- **Hardcoded codes** — every check has a unique SDC-NNN code (SDC-001..043 for errors/warnings, SDC-060..063 for clock relations, SDC-100..132 for info)
- **Zero external dependencies** — pure Python stdlib (`re`, `dataclasses`)

### Check Categories

| Severity | Count | Codes | Meaning |
|----------|-------|-------|---------|
| `error` | 11 | SDC-001..011 | Must fix — synthesis will produce wrong results |
| `warning` | 21 | SDC-020..045, 060..061 | Should review — potential design issues |
| `info` | 20+ | SDC-100..132 | Best practices — improve quality and correlation |

### Key Checks (subset)

**Errors:**
- SDC-001: No `create_clock` defined → no timing reference
- SDC-002: Duplicate clock names → silent overwrite
- SDC-005/006: No `set_input_delay` / `set_output_delay` → ports unconstrained
- SDC-008/009: I/O delay ≥ clock period → timing closure impossible

**Warnings:**
- SDC-020: Suspicious false path (no async/scan keywords)
- SDC-021: Multicycle without hold fix → false hold violations
- SDC-024: Multiple clocks without `set_clock_groups` → CDC un-flagged
- SDC-030: No `set_propagated_clock` → ideal clock is over-optimistic

**Info:**
- SDC-100: Missing `sdc_version`
- SDC-115: Missing `set_timing_derate`
- SDC-123: Missing power constraints

---

## Use Cases

| Scenario | Why |
|----------|-----|
| **Pre-synthesis signoff** | Catch errors before a 48-hour synthesis run |
| **CI/CD pipeline gate** | Reject commits that introduce constraint bugs |
| **New engineer onboarding** | Learn SDC best practices from automated feedback |
| **Constraint review meetings** | Generate a consistent checklist for peer review |
| **Multi-team handoff** | Ensure IP blocks meet minimum constraint quality |

---

## Structural View

```
┌──────────────┐     ┌──────────────────┐     ┌────────────────┐
│  SDC File    │────▶│  checker.py      │────▶│  CheckResult   │
│  (.sdc/.tcl) │     │  check_sdc(text) │     │  ┌──────────┐  │
└──────────────┘     │                  │     │  │ issues[] │  │
                     │  1. Regex-parse  │     │  │  .code   │  │
                     │     30+ commands │     │  │  .sev    │  │
                     │  2. 11 error     │     │  │  .msg    │  │
                     │     checks       │     │  ├──────────┤  │
                     │  3. 21 warning   │     │  │ info[]   │  │
                     │     checks       │     │  ├──────────┤  │
                     │  4. 20+ info     │     │  │ stats{}  │  │
                     │     checks       │     │  └──────────┘  │
                     │  5. Clock relns  │     └────────────────┘
                     │     integration  │
                     └──────────────────┘
```

## Flow Diagram

```
SDC Text Input
      │
      ▼
┌────────────────────────────────────────────┐
│  _grab() — Extract all commands via regex  │
│  • create_clock, create_generated_clock    │
│  • set_input_delay, set_output_delay       │
│  • set_false_path, set_multicycle_path     │
│  • set_timing_derate, set_operating_cond   │
│  • 30+ total command patterns              │
└────────────────────────────────────────────┘
      │
      ▼
┌────────────────────────────────────────────┐
│  ERROR CHECKS (SDC-001..011)              │
│  ┌───────┐  ┌──────────┐  ┌────────────┐  │
│  │No clk │  │Dup names│  │No I/O dly  │ ...│
│  └───────┘  └──────────┘  └────────────┘  │
└────────────────────────────────────────────┘
      │
      ▼
┌────────────────────────────────────────────┐
│  WARNING CHECKS (SDC-020..045)            │
│  ┌──────┐  ┌───────┐  ┌────────┐  ┌───┐  │
│  │False │  │No hold│  │No prop│  │Der│ ...│
│  │paths │  │  fix  │  │clocks │  │ate│    │
│  └──────┘  └───────┘  └────────┘  └───┘  │
└────────────────────────────────────────────┘
      │
      ▼
┌────────────────────────────────────────────┐
│  CLOCK RELATIONS (SDC-060..063)           │
│  • Imports clock_relations.analyze()      │
│  • Adds mismatches as warnings            │
└────────────────────────────────────────────┘
      │
      ▼
┌────────────────────────────────────────────┐
│  INFO SUGGESTIONS (SDC-100..132)          │
│  • Best practices and missing items       │
│  • Non-blocking recommendations           │
└────────────────────────────────────────────┘
      │
      ▼
┌────────────────────────────────────────────┐
│  CheckResult                               │
│  • issues: [Issue(code, sev, msg)]        │
│  • info:   [InfoItem(code, msg)]          │
│  • stats:  {Clocks: N, Input delays: M}   │
│  • .errors / .warnings (filtered)         │
└────────────────────────────────────────────┘
```

---

## CLI Usage

```bash
# Basic check
sdc-tools check my_design.sdc

# With verbose info and stats
sdc-tools check my_design.sdc --verbose

# JSON output for programmatic consumption
sdc-tools check my_design.sdc --json

# JUnit XML for CI integration
sdc-tools check my_design.sdc --junit --output results.xml

# With custom rules
sdc-tools check my_design.sdc --custom-rules my_policy.yaml

# Save report to file
sdc-tools check my_design.sdc --output check_report.txt
```

## Python API

```python
from checker import check_sdc

with open("design.sdc") as f:
    text = f.read()

result = check_sdc(text)

print(f"{len(result.errors)} errors, {len(result.warnings)} warnings")
for issue in result.issues:
    print(f"  [{issue.code}] {issue.sev.upper()}: {issue.msg}")

access result.info      # list of InfoItem
access result.stats     # dict with counts of all command types
```

## Checker Integration Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    checker.py (core)                         │
│  check_sdc(text) → CheckResult                              │
│    ├── Parses SDC (30+ regex patterns)                      │
│    ├── Runs 40+ checks                                      │
│    └── Imports clock_relations.analyze_clock_relations()    │
│         └── adds SDC-060..063 results                       │
└─────────────────────────────────────────────────────────────┘
         │
         ├──▶ cli.py: cmd_check() → text/JSON/JUnit output
         │
         └──▶ app.py: Checker tab → Streamlit UI
                   ├── Upload/paste SDC
                   ├── Summary metrics (4 cards)
                   ├── Expandable issues
                   ├── Info suggestions
                   ├── Custom rules YAML upload
                   └── Rule Reference table
```

## Configuration

The checker has no configuration file — all checks are hardcoded and always run. Custom validation policies can be added via `--custom-rules` (see [Custom Rules Engine](README-07-custom-rules.md)).

---

*Part of SDC Tools — an open-source VLSI constraint development toolkit.*