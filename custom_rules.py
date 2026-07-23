"""
SDC Tools — Custom Rules Engine
Load user-defined validation rules from YAML files and apply them to SDC text.
Extends the built-in checker with project-specific policies.

YAML format:
    rules:
      - id: MY-001
        name: "Clock period limit"
        severity: warning          # error | warning | info
        description: "Flag clocks with period > 10ns"
        command: create_clock      # SDC command to search for
        condition: value_above     # present | absent | count_above | count_below
                                  # value_above | value_below | regex_match
        field: period              # for value_* conditions: field name to extract
        threshold: 10.0            # for count/value conditions
        pattern: "-period\\s+(\\d+\\.?\\d*)"  # for regex_match: regex to match
        message: "Clock {name} has period {value}ns > 10ns"
"""

import re
import os
import glob
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # graceful fallback — YAML not available


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class CustomRule:
    """A single custom validation rule."""
    id: str                          # "MY-001"
    name: str                        # Human-readable name
    severity: str                    # "error" | "warning" | "info"
    description: str                 # What this rule checks
    command: str                     # SDC command to search for, e.g. "create_clock"
    condition: str                   # "present" | "absent" | "count_above" | etc.
    field_name: str = ""             # For value_* conditions
    threshold: float = 0.0           # For count/value conditions
    pattern: str = ""                # For regex_match condition
    message: str = ""                # Custom message template
    tags: List[str] = field(default_factory=list)   # e.g. ["policy", "signoff"]
    enabled: bool = True


@dataclass
class CustomRuleResult:
    """Result of applying a custom rule."""
    rule: CustomRule
    passed: bool
    msg: str
    matches: List[str] = field(default_factory=list)  # raw matched lines


@dataclass
class CustomRuleset:
    """A collection of rules loaded from a YAML file."""
    name: str = ""
    version: str = ""
    description: str = ""
    rules: List[CustomRule] = field(default_factory=list)
    source_file: str = ""


# ── YAML Loading ─────────────────────────────────────────────────────────────

def load_ruleset(yaml_path: str) -> CustomRuleset:
    """Load a single YAML ruleset file."""
    if yaml is None:
        raise ImportError(
            "PyYAML is required for custom rules. Install with: pip install pyyaml"
        )

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data or "rules" not in data:
        raise ValueError(f"Invalid ruleset file: {yaml_path} — expected 'rules' key")

    rules = []
    for r in data["rules"]:
        if not r.get("id") or not r.get("command") or not r.get("condition"):
            continue  # skip malformed rules
        rules.append(CustomRule(
            id=r["id"],
            name=r.get("name", r["id"]),
            severity=r.get("severity", "warning"),
            description=r.get("description", ""),
            command=r["command"],
            condition=r["condition"],
            field_name=r.get("field", ""),
            threshold=float(r.get("threshold", 0)),
            pattern=r.get("pattern", ""),
            message=r.get("message", ""),
            tags=r.get("tags", []),
            enabled=r.get("enabled", True),
        ))

    return CustomRuleset(
        name=data.get("name", Path(yaml_path).stem),
        version=data.get("version", "1.0"),
        description=data.get("description", ""),
        rules=rules,
        source_file=yaml_path,
    )


def load_rulesets_from_dir(directory: str) -> List[CustomRuleset]:
    """Load all .yaml/.yml files from a directory."""
    patterns = glob.glob(os.path.join(directory, "*.yaml")) + \
               glob.glob(os.path.join(directory, "*.yml"))
    rulesets = []
    for path in sorted(patterns):
        try:
            rulesets.append(load_ruleset(path))
        except Exception as e:
            print(f"Warning: cannot load {path}: {e}")
    return rulesets


# ── Rule Application ────────────────────────────────────────────────────────

# Condition handlers
_CONDITIONS = {}


def _cond(condition_name):
    """Decorator to register a condition handler."""
    def decorator(fn):
        _CONDITIONS[condition_name] = fn
        return fn
    return decorator


@_cond("present")
def _check_present(cmds: List[str], rule: CustomRule, text: str) -> tuple[bool, str]:
    if cmds:
        return True, f"Found {len(cmds)} {rule.command} command(s)"
    return False, f"No {rule.command} found"


@_cond("absent")
def _check_absent(cmds: List[str], rule: CustomRule, text: str) -> tuple[bool, str]:
    if not cmds:
        return True, f"No {rule.command} found (as expected)"
    return False, f"Found {len(cmds)} {rule.command} command(s) — should be absent"


@_cond("count_above")
def _check_count_above(cmds: List[str], rule: CustomRule, text: str) -> tuple[bool, str]:
    count = len(cmds)
    if count > rule.threshold:
        return False, f"Found {count} {rule.command} commands — exceeds threshold of {int(rule.threshold)}"
    return True, f"Found {count} {rule.command} command(s) (threshold: {int(rule.threshold)})"


@_cond("count_below")
def _check_count_below(cmds: List[str], rule: CustomRule, text: str) -> tuple[bool, str]:
    count = len(cmds)
    if count < rule.threshold:
        return False, f"Found {count} {rule.command} commands — below threshold of {int(rule.threshold)}"
    return True, f"Found {count} {rule.command} command(s) (threshold: {int(rule.threshold)})"


@_cond("count_exactly")
def _check_count_exactly(cmds: List[str], rule: CustomRule, text: str) -> tuple[bool, str]:
    count = len(cmds)
    if count != int(rule.threshold):
        return False, f"Found {count} {rule.command} commands — expected exactly {int(rule.threshold)}"
    return True, f"Found {count} {rule.command} command(s)"


@_cond("value_above")
def _check_value_above(cmds: List[str], rule: CustomRule, text: str) -> tuple[bool, str]:
    if not cmds:
        return True, f"No {rule.command} to check"
    pattern = rule.pattern or rf'-{rule.field_name}\s+([\d.]+)'
    for cmd in cmds:
        m = re.search(pattern, cmd)
        if m:
            val = float(m.group(1))
            if val > rule.threshold:
                return False, f"Found value {val} in {rule.command} — exceeds {rule.threshold}"
    return True, f"All values within threshold ({rule.threshold})"


@_cond("value_below")
def _check_value_below(cmds: List[str], rule: CustomRule, text: str) -> tuple[bool, str]:
    if not cmds:
        return True, f"No {rule.command} to check"
    pattern = rule.pattern or rf'-{rule.field_name}\s+([\d.]+)'
    for cmd in cmds:
        m = re.search(pattern, cmd)
        if m:
            val = float(m.group(1))
            if val < rule.threshold:
                return False, f"Found value {val} in {rule.command} — below {rule.threshold}"
    return True, f"All values within threshold ({rule.threshold})"


@_cond("regex_match")
def _check_regex_match(cmds: List[str], rule: CustomRule, text: str) -> tuple[bool, str]:
    if not rule.pattern:
        return True, "No pattern defined"
    matches = []
    for cmd in cmds:
        if re.search(rule.pattern, cmd):
            matches.append(cmd.strip()[:80])
    if matches:
        return False, f"Found {len(matches)} match(es) for pattern in {rule.command}"
    return True, f"No matches for pattern in {rule.command}"


@_cond("regex_absent")
def _check_regex_absent(cmds: List[str], rule: CustomRule, text: str) -> tuple[bool, str]:
    if not rule.pattern:
        return True, "No pattern defined"
    matches = []
    for cmd in cmds:
        if re.search(rule.pattern, cmd):
            matches.append(cmd.strip()[:80])
    if matches:
        return False, f"Found {len(matches)} match(es) — pattern should NOT match"
    return True, "No forbidden patterns found"


def apply_rules(text: str, ruleset: CustomRuleset) -> List[CustomRuleResult]:
    """Apply all enabled rules from a ruleset to SDC text."""
    results = []
    for rule in ruleset.rules:
        if not rule.enabled:
            continue

        # Find all commands matching the rule's command pattern
        pattern = rf'{re.escape(rule.command)}[^;\n]*'
        cmds = re.findall(pattern, text, re.MULTILINE)

        # Dispatch to condition handler
        handler = _CONDITIONS.get(rule.condition)
        if handler is None:
            results.append(CustomRuleResult(
                rule=rule, passed=False,
                msg=f"Unknown condition: {rule.condition}",
            ))
            continue

        passed, msg = handler(cmds, rule, text)

        # Apply custom message template if provided
        if rule.message and not passed:
            # Replace {count}, {value}, {name} placeholders
            count = len(cmds)
            value = ""
            if rule.pattern and cmds:
                m = re.search(rule.pattern, cmds[0])
                if m:
                    value = m.group(1)
            msg = rule.message.replace("{count}", str(count)).replace("{value}", value)

        results.append(CustomRuleResult(
            rule=rule,
            passed=passed,
            msg=msg,
            matches=[c.strip()[:120] for c in cmds[:5]],  # first 5 matches
        ))

    return results


def apply_rulesets(text: str, rulesets: List[CustomRuleset]) -> Dict[str, List[CustomRuleResult]]:
    """Apply multiple rulesets. Returns {ruleset_name: [results]}."""
    all_results = {}
    for rs in rulesets:
        all_results[rs.name] = apply_rules(text, rs)
    return all_results


# ── Integration with Checker ────────────────────────────────────────────────

def integrate_with_check(text: str, rules_dirs: List[str] = None) -> tuple:
    """Run built-in checker + custom rules, return combined result.

    Returns (CheckResult, custom_results_dict).
    """
    from checker import check_sdc

    result = check_sdc(text)

    custom_results = {}
    if rules_dirs:
        for d in rules_dirs:
            if os.path.isdir(d):
                rulesets = load_rulesets_from_dir(d)
                custom_results.update(apply_rulesets(text, rulesets))

    return result, custom_results


# ── Built-in Example Rules ──────────────────────────────────────────────────

EXAMPLE_RULES_YAML = """\
# SDC Tools — Example Custom Rules
# Copy this file and modify for your project's policies.
name: Example Rules
version: "1.0"
description: Example custom validation rules for SDC files

rules:
  # ── Clock Policies ────────────────────────────────────────────────────
  - id: MY-001
    name: "Clock period maximum"
    severity: warning
    description: "Flag any clock with period above 10ns (frequency below 100MHz)"
    command: create_clock
    condition: value_above
    field: period
    threshold: 10.0
    message: "Clock period {value}ns exceeds 10ns limit"

  - id: MY-002
    name: "Require set_propagated_clock"
    severity: error
    description: "All designs must use set_propagated_clock for post-layout correlation"
    command: set_propagated_clock
    condition: present
    message: "No set_propagated_clock found — required by project policy"

  - id: MY-003
    name: "Require set_clock_uncertainty"
    severity: error
    description: "Clock uncertainty must be defined"
    command: set_clock_uncertainty
    condition: present
    message: "No set_clock_uncertainty — required for timing closure"

  # ── I/O Policies ─────────────────────────────────────────────────────
  - id: MY-004
    name: "Require input delay"
    severity: error
    description: "All inputs must be constrained"
    command: set_input_delay
    condition: present
    message: "No set_input_delay — input ports unconstrained"

  - id: MY-005
    name: "Require output delay"
    severity: error
    description: "All outputs must be constrained"
    command: set_output_delay
    condition: present
    message: "No set_output_delay — output ports unconstrained"

  # ── Derate Policies ──────────────────────────────────────────────────
  - id: MY-006
    name: "Require timing derate"
    severity: warning
    description: "AOCV derate must be defined for signoff"
    command: set_timing_derate
    condition: present
    message: "No set_timing_derate — needed for advanced node signoff"

  - id: MY-007
    name: "Require operating conditions"
    severity: warning
    description: "PVT corner must be specified"
    command: set_operating_conditions
    condition: present
    message: "No set_operating_conditions — PVT corner unspecified"

  # ── Design Rule Policies ─────────────────────────────────────────────
  - id: MY-008
    name: "Max false paths"
    severity: warning
    description: "More than 20 false paths suggests over-constraining"
    command: set_false_path
    condition: count_above
    threshold: 20
    message: "Found {count} false paths — review each one"

  - id: MY-009
    name: "Max multicycle paths"
    severity: info
    description: "More than 15 multicycle paths needs documentation"
    command: set_multicycle_path
    condition: count_above
    threshold: 15
    message: "Found {count} multicycle paths — document each one"

  - id: MY-010
    name: "Require set_dont_use"
    severity: info
    description: "Exclude problematic cells from synthesis"
    command: set_dont_use
    condition: present
    message: "No set_dont_use — consider excluding weak/problematic cells"
"""
