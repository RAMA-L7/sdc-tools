# Feature 7: Custom Rules Engine

> **Module:** `custom_rules.py` · **CLI:** `sdc-tools check --custom-rules` · **UI:** Checker Tab (YAML upload) · **Example:** `custom_rules_example.yaml`

---

## Why It's Needed

The built-in SDC Checker has 40+ hardcoded rules — but every design team, foundry, and project has **additional policies** that can't be hardcoded:

- _"Clock periods must be ≥ 10ns on this chip"_ (foundry frequency limit)
- _"No more than 20 false paths without director approval"_ (process-specific review policy)
- _"All blocks must include set_clock_latency and set_clock_transition"_ (team coding standard)
- _"Derate -cell_delay must not exceed 1.10"_ (foundry signoff requirement)

The Custom Rules Engine lets teams define these policies in simple YAML files and run them alongside the built-in checker — no Python coding required.

---

## How It Was Implemented

### Architecture

- **YAML-based rule definitions** — each rule is a dict with id, name, severity, command, condition, and optional parameters
- **Decorator-based condition handlers** — 9 conditions registered via `@_cond(name)` pattern
- **`CustomRuleset`** — a named collection of rules loaded from one YAML file
- **`CustomRuleResult`** — per-rule result with passed/failed, message, and matching lines
- **PyYAML dependency** — optional; graceful `ImportError` fallback with clear install instructions

### 9 Condition Types

| Condition | What It Checks | Parameters |
|-----------|---------------|------------|
| `present` | SDC command must exist | `command` |
| `absent` | SDC command must NOT exist | `command` |
| `count_above` | Command count > threshold | `command`, `threshold` |
| `count_below` | Command count < threshold | `command`, `threshold` |
| `count_exactly` | Command count == threshold | `command`, `threshold` |
| `value_above` | A field value > threshold | `command`, `field`, `pattern`, `threshold` |
| `value_below` | A field value < threshold | `command`, `field`, `pattern`, `threshold` |
| `regex_match` | Pattern must NOT match in commands | `command`, `pattern` |
| `regex_absent` | Pattern must NOT match anywhere | `pattern` |

### Rule Severity Levels

| Severity | Meaning | UI Icon |
|----------|---------|---------|
| `error` | Must fix — blocks signoff | 🔴 |
| `warning` | Should review | 🟡 |
| `info` | Recommendation | ℹ️ |

---

## Use Cases

| Scenario | Example Rule |
|----------|-------------|
| **Foundry frequency limit** | "All clock periods must be ≤ 10ns" (value_above on create_clock) |
| **Team coding standard** | "All blocks must have set_propagated_clock" (present on set_propagated_clock) |
| **Signoff checklist** | "Derate required for all advanced-node designs" (present on set_timing_derate) |
| **Process policy** | "No more than 10 disable_timing commands without review" (count_above) |
| **Design rule audit** | "No set_dont_use without documentation" (present on set_dont_use) |

---

## Structural View

```
┌────────────────────────┐
│  custom_rules_example  │
│  .yaml                 │
│  ┌────────────────┐    │
│  │ name: Example  │    │
│  │ rules:         │    │
│  │  - id: MY-001  │    │
│  │    command:    │    │
│  │     create_clk │    │
│  │    condition:  │    │
│  │     value_above │   │
│  │    threshold:  │    │
│  │     10.0       │    │
│  └────────────────┘    │
└────────────────────────┘
         │
         ▼ (load YAML)
┌────────────────────────┐
│  load_ruleset(path)    │
│  → CustomRuleset       │
│    ├── name            │
│    ├── version         │
│    ├── description     │
│    └── rules[]         │
│       └── CustomRule   │
└────────────────────────┘
         │
         ▼ (apply to SDC)
┌────────────────────────┐
│  apply_rules(text,     │
│    ruleset)            │
│  → [CustomRuleResult]  │
│                        │
│  For each enabled rule: │
│  1. Find matching cmds │
│  2. Dispatch to        │
│     condition handler  │
│  3. Return result      │
└────────────────────────┘
```

## Flow Diagram

```
YAML Rule Definition
    │
    ▼
┌─────────────────────────────────────────────┐
│  load_ruleset(yaml_path)                    │
│                                             │
│  yaml.safe_load(file) → data                │
│  for r in data["rules"]:                    │
│    CustomRule(                               │
│      id=r["id"],                            │
│      command=r["command"],                  │
│      condition=r["condition"],              │
│      threshold=r.get("threshold", 0),       │
│      field=r.get("field", ""),              │
│      pattern=r.get("pattern", ""),          │
│      ...                                    │
│    )                                        │
│  return CustomRuleset(rules=rules, ...)      │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│  apply_rules(sdc_text, ruleset)             │
│                                             │
│  results = []                               │
│  for rule in ruleset.rules:                 │
│    if not rule.enabled: continue            │
│                                             │
│    # Find matching SDC commands             │
│    pattern = rf'{command}[^;\n]*'          │
│    cmds = re.findall(pattern, text)         │
│                                             │
│    # Dispatch to handler                    │
│    handler = _CONDITIONS[rule.condition]    │
│    passed, msg = handler(cmds, rule, text)  │
│                                             │
│    # Apply message template                 │
│    if rule.message and not passed:          │
│      replace {count}, {value}               │
│                                             │
│    results.append(CustomRuleResult(...))    │
│                                             │
│  return results                             │
└─────────────────────────────────────────────┘
    │
    ├──▶ CLI: check --custom-rules my_rules.yaml
    │
    └──▶ UI: Upload YAML in Checker tab
          → Results shown as PASS/FAIL
          → Expandable per-rule details
```

## YAML Rule Format

```yaml
name: My Team Rules
version: "1.0"
description: Custom SDC validation policies

rules:
  - id: MY-001
    name: "Clock period maximum"
    severity: warning
    description: "Flag clocks with period > 10ns"
    command: create_clock
    condition: value_above
    field: period
    threshold: 10.0
    pattern: "-period\\s+(\\d+\\.?\\d*)"
    message: "Clock period {value}ns exceeds 10ns limit"
    tags: ["policy", "frequency"]
    enabled: true

  - id: MY-002
    name: "Require set_propagated_clock"
    severity: error
    description: "All designs must use propagated clocks"
    command: set_propagated_clock
    condition: present
    message: "No set_propagated_clock — required by policy"
```

## CLI Usage

```bash
# Single custom rules file
sdc-tools check design.sdc --custom-rules my_policy.yaml

# Multiple rules files (repeatable)
sdc-tools check design.sdc \
  --custom-rules team_policy.yaml \
  --custom-rules foundry_requirements.yaml

# With JSON output (custom rules included in data)
sdc-tools check design.sdc --custom-rules my_policy.yaml --json
```

## Python API

```python
from custom_rules import load_ruleset, apply_rules, load_rulesets_from_dir

# Load a single ruleset
ruleset = load_ruleset("my_policy.yaml")
print(f"Loaded: {ruleset.name} v{ruleset.version} ({len(ruleset.rules)} rules)")

# Apply to SDC text
with open("design.sdc") as f:
    text = f.read()

results = apply_rules(text, ruleset)
for r in results:
    status = "✅ PASS" if r.passed else "❌ FAIL"
    print(f"{status} {r.rule.id}: {r.msg}")

# Load all YAML files from a directory
rulesets = load_rulesets_from_dir("./project_policies/")

# Integration with built-in checker
from custom_rules import integrate_with_check
result, custom_results = integrate_with_check(text, rules_dirs=["./policy/"])
```

## Built-in Example Rules

The `custom_rules.py` module includes an `EXAMPLE_RULES_YAML` constant (10 rules) and `custom_rules_example.yaml` file:

| Rule | Condition | Purpose |
|------|-----------|---------|
| MY-001 | value_above on period | Clock period ≤ 10ns |
| MY-002 | present: propagated_clock | Must use propagated clocks |
| MY-003 | present: clock_uncertainty | Must define uncertainty |
| MY-004 | present: input_delay | Input ports constrained |
| MY-005 | present: output_delay | Output ports constrained |
| MY-006 | present: timing_derate | AOCV derate required |
| MY-007 | present: operating_conditions | PVT corner specified |
| MY-008 | count_above on false_paths | Max 20 false paths |
| MY-009 | count_above on multicycle | Max 15 multicycle |
| MY-010 | present: dont_use | Must exclude weak cells |

---

*Part of SDC Tools — an open-source VLSI constraint development toolkit.*