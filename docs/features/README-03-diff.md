# Feature 3: Constraint Change Analyzer (Semantic Diff)

> **Module:** `constraint_diff.py` · **CLI:** `sdc-tools diff` · **UI:** Change Analyzer Tab · **Codes:** CHG-FP-001..CHG-GEN-003

**Dependencies:** `tcl_resolver.py` (TCL variable resolution), `wildcard_analyzer.py` (wildcard drift detection)

---

## Why It's Needed

A text-based `diff` between two SDC files shows _what changed_ but not _what it means_. Constraint changes that look harmless often cause thousands of timing violations:

- A variable value changes from `$CYCLE=4` to `$CYCLE=5` in a linked TCL file — text diff shows nothing
- A `set_false_path -from A -to B` is removed — text diff shows one line gone, but every path from A→B becomes timing-checked
- A wildcard changes from `[all_registers]` to `[get_cells *slow*]` — fewer objects matched, some paths slip through

The Constraint Change Analyzer performs **semantic comparison**: it parses both versions, resolves variable references, matches constraints by intent, and classifies each change's severity (fatal / warning / info) with engineering context explaining the impact.

Inspired by [Ausdia TimeVision](https://www.ausdia.com/blog/6/not-much-change-in-constraints-leads-to-thousands-of-violations/filter/0).

---

## How It Was Implemented

### Three-Pipeline Architecture

1. **TCL Variable Resolution** (`tcl_resolver.py`)
   - Parses `set VARNAME value` assignments
   - Resolves `$VARNAME` and `${VARNAME}` references (up to 5 levels deep)
   - Tracks source file origin (linked TCL files + main SDC)

2. **Constraint Parsing & Matching** (`constraint_diff.py`)
   - 19 command-specific parsers (each with field extraction)
   - Variable-parameterized text resolved before parsing
   - Constraints matched between versions by computed comparison key

3. **Change Classification** (`wildcard_analyzer.py` + `constraint_diff.py`)
   - 20 change rules with severity classification
   - Wildcard drift detection: narrowed / broadened / rewritten
   - Generates human-readable impact explanation for each change

### Change Severity Levels

| Severity | Meaning | Count | Example |
|----------|---------|-------|---------|
| `fatal` | Causes timing violations | 6 | False path removed, clock port changed |
| `warning` | Significantly changes timing | 10 | I/O delay changed, derate value changed |
| `info` | Notable but not immediately dangerous | 4 | New constraint added, constraint modified |

### Change Rules (20 total)

| Code | Description | Severity |
|------|-------------|----------|
| CHG-FP-001 | False path removed | fatal |
| CHG-FP-002 | False path target changed | fatal |
| CHG-FP-003 | New false path added | info |
| CHG-MCP-001 | Multicycle removed | fatal |
| CHG-MCP-002 | Multicycle setup decreased | fatal |
| CHG-MCP-003 | Multicycle increased | warning |
| CHG-MCP-004 | Hold multicycle missing | fatal |
| CHG-CK-001 | Clock period decreased | warning |
| CHG-CK-005 | Generated clock divider changed | fatal |
| CHG-DR-001 | Cell early derate reduced | warning |
| CHG-DR-002 | Cell late derate increased | warning |
| CHG-WC-001 | Wildcard pattern changed | warning |
| CHG-IO-001 | I/O delay value changed | warning |
| CHG-OC-001 | Operating conditions changed | warning |
| CHG-GEN-001 | New constraint added | info |
| CHG-GEN-002 | Constraint removed | info |
| CHG-GEN-003 | Non-critical field changed | info |

---

## Use Cases

| Scenario | Why |
|----------|-----|
| **ECO review** | Compare pre-ECO vs post-ECO constraints — catch unintended changes |
| **Version upgrade** | Validate constraint migration between tool versions |
| **IP integration** | Verify third-party IP constraints don't conflict with chip-level SDC |
| **Design handoff** | Document what changed between RTL freeze and tapeout |
| **CI gate** | Reject PRs that introduce fatal constraint changes |

---

## Structural View

```
┌──────────┐     ┌─────────────────┐     ┌────────────────┐
│  SDC V1  │────▶│ tcl_resolver.py │────▶│ Variable       │
│          │     │ build_symbol()  │     │ Resolution     │
└──────────┘     └─────────────────┘     └────────────────┘
                                                    │
┌──────────┐     ┌─────────────────┐               │
│  SDC V2  │────▶│ tcl_resolver.py │────▶ Variable   │
│          │     │                 │     Resolution  │
└──────────┘     └─────────────────┘               │
                                                    ▼
┌──────────────────────────────────────────────────────────┐
│  constraint_diff.py                                       │
│                                                           │
│  1. parse_sdc_constraints(V1_resolved) → List[Constraint] │
│  2. parse_sdc_constraints(V2_resolved) → List[Constraint] │
│                                                           │
│  3. _match_constraints(c1, c2)                            │
│     → (matched_pairs, only_in_v1, only_in_v2)            │
│       ┌──────────────────────────────────────┐            │
│       │  Matched by comparison key:          │            │
│       │  "clk:clk_core"  "fp:A:B"  "mcp:C:D"│            │
│       └──────────────────────────────────────┘            │
│                                                           │
│  4. classify_changes(matched, only_v1, only_v2)          │
│     → List[ConstraintChange]                              │
│       ├── Removed → CHG-FP-001, CHG-MCP-001, ...         │
│       ├── Added   → CHG-FP-003, CHG-GEN-001, ...         │
│       └── Modified → field-by-field comparison            │
│             ├── False path fields → check wildcard drift  │
│             ├── Clock period → CHG-CK-001                 │
│             ├── Derate value → CHG-DR-001/002             │
│             └── I/O delay → CHG-IO-001                    │
└──────────────────────────────────────────────────────────┘
      │
      ▼
┌──────────────────────────────────────┐
│  ChangeAnalysisResult                 │
│  ├── changes: List[ConstraintChange] │
│  ├── .fatal_changes (severity=fatal) │
│  ├── .warnings (severity=warning)    │
│  ├── .info_changes (severity=info)   │
│  └── stats: Dict[str, int]           │
└──────────────────────────────────────┘
```

## Flow Diagram

```
  V1 SDC (.sdc)      V2 SDC (.sdc)
       │                   │
       ▼                   ▼
 ┌──────────┐       ┌──────────┐
 │ TCL Var  │       │ TCL Var  │
 │ Resolver │       │ Resolver │
 └────┬─────┘       └────┬─────┘
      │                  │
      ▼                  ▼
 ┌──────────┐       ┌──────────┐
 │ Parse 19 │       │ Parse 19 │
 │ commands │       │ commands │
 └────┬─────┘       └────┬─────┘
      │                  │
      └──────┬───────────┘
             ▼
    ┌──────────────────┐
    │  Match by key    │
    │  (semantic, not  │
    │   text position) │
    └────┬──────┬──────┘
         │      │
         ▼      ▼
   ┌────────┐  ┌────────┐
   │Matched │  │Unmatched│
   │Pairs   │  │(V1 only │
   │        │  │ or V2   │
   │        │  │ only)   │
   └───┬────┘  └────┬───┘
       │            │
       ▼            ▼
  ┌──────────┐  ┌──────────┐
  │Field diff│  │Added/    │
  │per pair  │  │Removed   │
  └────┬─────┘  └────┬─────┘
       │             │
       ▼             ▼
  ┌────────────────────────┐
  │  Classify with rules   │
  │  ┌────────────────────┐│
  │  │CHG-FP-001 fatal    ││
  │  │CHG-CK-001 warning  ││
  │  │CHG-GEN-001 info    ││
  │  └────────────────────┘│
  └────────────────────────┘
```

---

## CLI Usage

```bash
# Basic diff
sdc-tools diff old.sdc new.sdc

# With linked TCL variable files
sdc-tools diff old.sdc new.sdc \
  --linked-v1 params_v1.tcl \
  --linked-v2 params_v2.tcl

# JSON output
sdc-tools diff old.sdc new.sdc --json

# Verbose (show V1/V2 text per change)
sdc-tools diff old.sdc new.sdc --verbose

# Save to file
sdc-tools diff old.sdc new.sdc --output diff_report.txt
```

## Python API

```python
from constraint_diff import analyze_constraint_changes

with open("old.sdc") as f: v1 = f.read()
with open("new.sdc") as f: v2 = f.read()

result = analyze_constraint_changes(v1, v2)

print(f"{len(result.fatal_changes)} fatal changes")
for c in result.fatal_changes:
    print(f"  [{c.rule.rule_id}] {c.explanation}")
    print(f"    V1: {c.v1_text}")
    print(f"    V2: {c.v2_text}")

print(f"{len(result.warnings)} warnings")
print(f"{len(result.info_changes)} info items")
print(f"Stats: {result.stats}")
```

## Wildcard Analyzer Integration

The `wildcard_analyzer.py` module provides pattern-level comparison:
- **Parses** collection expressions like `[get_cells *slow*]`, `[all_registers]`
- **Classifies** specificity: broad / moderate / specific / exact
- **Scores** risk: 0 (safe) to 10 (dangerous)
- **Compares** V1 vs V2 patterns: narrowed / broadened / rewritten
- Integrated into the diff flow for `set_false_path` wildcard changes

---

*Part of SDC Tools — an open-source VLSI constraint development toolkit.*