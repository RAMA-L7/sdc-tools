# Feature 8: Rules Registry

> **Module:** `rules_registry.py` · **CLI:** `sdc-tools rules` · **UI:** Rule Reference (Checker tab sidebar) · **Codes:** All SDC-NNN, CHG-XXX-NNN

---

## Why It's Needed

With 60+ rule codes (SDC-001..126, CHG-FP-001..GEN-003) spread across 5 modules, users had no way to look up what a code means without either:
- Reading the full message when it's displayed
- Grepping the source code
- Remembering from experience

The Rules Registry centralizes every rule code with:
- **Human-readable name** — `"Missing Clock Definition"`, not just SDC-001
- **Description** — what the check detects
- **Engineering context** — _why_ it matters in real designs
- **Fix guidance** — how to resolve it
- **External references** — links to Synopsys docs, Ausdia blogs
- **Module origin** — which tool produces this code
- **Version tracking** — when each rule was introduced

---

## How It Was Implemented

### Data Model

- **`Rule` dataclass** — code, severity, short_name, description, why_matters, fix, reference_url, module, added_version
- **`RULES` dictionary** — code → Rule, populated by `_r()` helper
- **Package-level `APP_VERSION`** — "1.2.0"
- **4 lookup functions** — `get_all_rules()`, `get_rules_by_module()`, `get_rule()`, `get_rules_by_severity()`

### Rule Categories

| Module | Codes | Count | Severities |
|--------|-------|-------|------------|
| `checker` | SDC-001..045, SDC-100..126, 140 | 45 | error, warning, info |
| `mmc` | SDC-050..054 | 4 | warning, info |
| `clock_relations` | SDC-060..063 | 4 | warning, info |
| `constraint_diff` | CHG-FP-001..003, CHG-MCP-001..004, CHG-CK-001..005, CHG-DR-001..002, CHG-WC-001..002, CHG-IO-001, CHG-OC-001, CHG-GEN-001..003 | 20 | fatal, warning, info |

### APP_VERSION Tracking

| Version | Rules Added |
|---------|-------------|
| 1.0.0 | SDC-001..045, SDC-100..126, CHG-* |
| 1.1.0 | MMC rules (SDC-050..054) |
| 1.2.0 | Clock relations (SDC-060..063), SDC-140, Clock relation analysis skipped |

---

## Use Cases

| Scenario | Why |
|----------|-----|
| **Quick lookup** | "What does SDC-060 mean?" → CLI or UI in 2 seconds |
| **Onboarding** | New engineers learn rule meanings without reading source code |
| **Audit** | List all rules by severity (e.g., "show me all fatal rules") |
| **Debugging** | Understand why a rule triggered with engineering context |
| **Version upgrade** | See what rules were added since the last version |

---

## Structural View

```
rules_registry.py
    │
    ├── APP_VERSION = "1.2.0"
    │
    ├── Rule dataclass (7 fields)
    │   ├── code, severity
    │   ├── short_name, description
    │   ├── why_matters, fix
    │   ├── reference_url
    │   └── module, added_version
    │
    ├── RULES: Dict[str, Rule] (60+ entries)
    │   ├── SDC-001..011  (checker errors)
    │   ├── SDC-020..045  (checker warnings)
    │   ├── SDC-050..054  (mmc)
    │   ├── SDC-060..063  (clock_relations)
    │   ├── SDC-100..126  (checker info)
    │   ├── SDC-130..132  (checker info, MMC-related)
    │   ├── SDC-140       (checker info, 1.2.0)
    │   ├── CHG-FP-001..003
    │   ├── CHG-MCP-001..004
    │   ├── CHG-CK-001..005
    │   ├── CHG-DR-001..002
    │   ├── CHG-WC-001..002
    │   ├── CHG-IO-001
    │   ├── CHG-OC-001
    │   └── CHG-GEN-001..003
    │
    └── Lookup functions
        ├── get_all_rules() → List[Rule]
        ├── get_rules_by_module(module) → List[Rule]
        ├── get_rule(code) → Rule | None
        └── get_rules_by_severity(severity) → List[Rule]
```

## Flow Diagram

```
User sees code in tool output:
    [SDC-060] Clocks CLKA/CLKB marked -asynchronous...
                │
                ▼
CLI: sdc-tools rules show SDC-060
                │
                ▼
┌──────────────────────────────────────────┐
│  get_rule("SDC-060")                     │
│    → RULES["SDC-060"]                    │
│      → Rule(                             │
│          code="SDC-060",                 │
│          severity="warning",              │
│          short_name="Async Instead of    │
│            Physically Exclusive",        │
│          description="Clock pair marked  │
│            -asynchronous but should be   │
│            -physically_exclusive...",    │
│          why_matters="-asynchronous      │
│            causes unnecessary SI...",    │
│          fix="Change to                 │
│            set_clock_groups              │
│            -physically_exclusive...",    │
│          reference_url="https://...",    │
│          module="clock_relations",       │
│          added_version="1.2.0",          │
│        )                                 │
└──────────────────────────────────────────┘
                │
                ▼
Output:
  Code:       SDC-060
  Severity:   warning
  Name:       Async Instead of Physically Exclusive
  Module:     clock_relations
  Added:      v1.2.0
  Description: Clock pair marked -asynchronous but should be...
  Why:        -asynchronous causes unnecessary Crosstalk/SI...
  Fix:        Change to set_clock_groups -physically_exclusive...
  Reference:  https://www.ausdia.com/blog/5/...
```

---

## CLI Usage

```bash
# List ALL rules
sdc-tools rules list

# List rules from a specific module
sdc-tools rules list --module checker
sdc-tools rules list --module constraint_diff

# Filter by severity
sdc-tools rules list --severity error
sdc-tools rules list --severity fatal

# Search by keyword
sdc-tools rules list --search derate
sdc-tools rules list --search clock

# Single rule details
sdc-tools rules show SDC-060
sdc-tools rules show CHG-FP-001

# JSON output
sdc-tools rules list --json
sdc-tools rules show SDC-001 --json
```

## Python API

```python
from rules_registry import (
    APP_VERSION, get_all_rules, get_rule,
    get_rules_by_module, get_rules_by_severity,
)

print(f"SDC Tools v{APP_VERSION}")

# Look up a single rule
rule = get_rule("SDC-060")
if rule:
    print(f"[{rule.code}] {rule.short_name}")
    print(f"  Severity: {rule.severity}")
    print(f"  Module: {rule.module}")
    print(f"  Why: {rule.why_matters}")
    print(f"  Fix: {rule.fix}")

# Get all fatal rules
for rule in get_rules_by_severity("fatal"):
    print(f"{rule.code}: {rule.short_name}")

# Get all rules for a module
for rule in get_rules_by_module("clock_relations"):
    print(f"{rule.code}: {rule.short_name} (v{rule.added_version})")

# Full list
all_rules = get_all_rules()
print(f"Total: {len(all_rules)} rules")
```

## UI: Rule Reference Table

In the Streamlit Checker tab, at the bottom:
- **Search box** — filter by code, name, description, or why_matters
- **Module filter** — All, checker, mmc, clock_relations, constraint_diff
- **Count badge** — shows filtered rule count
- **Each rule** expandable with full details: severity, module, description, why_matters, fix, reference URL
- **Severity icons** — 🔴 error, 🟡 warning, 🔵 info, 💀 fatal

---

*Part of SDC Tools — an open-source VLSI constraint development toolkit.*