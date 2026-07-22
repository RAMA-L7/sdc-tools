"""
TCL Variable Resolver for SDC files
Parse variable assignments, resolve $VARNAME references, track source file dependencies.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class VariableBinding:
    name: str                      # e.g. "CYCLE", "STATIC_PINS"
    raw_value: str                 # literal RHS text: "4", "[get_pins *static_inst*]"
    resolved_value: str            # after resolving nested $VARNAME refs
    source_file: str               # filename or "(pasted text)"
    line_number: int               # line in source
    is_collection: bool = False    # True if value contains [get_pins], [get_ports], etc.


@dataclass
class SymbolTable:
    variables: Dict[str, VariableBinding] = field(default_factory=dict)
    source_files: List[str] = field(default_factory=list)

    def resolve(self, text: str) -> str:
        """Replace all $VARNAME references in text with resolved values."""
        result = text
        for name, binding in sorted(self.variables.items(), key=lambda x: -len(x[0])):
            result = result.replace(f"${{{name}}}", binding.resolved_value)
            result = result.replace(f"${name}", binding.resolved_value)
        return result

    def get(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """Return resolved value of a variable, or default."""
        binding = self.variables.get(name)
        if binding:
            return binding.resolved_value
        return default

    def __repr__(self) -> str:
        return f"SymbolTable({len(self.variables)} vars, {len(self.source_files)} files)"


# ── Variable parsing ──────────────────────────────────────────────────────────

_COLLECTION_PATTERN = re.compile(
    r'\[(?:get_pins|get_ports|get_cells|get_clocks|get_nets|'
    r'all_inputs|all_outputs|all_clocks|all_registers|all_nets|current_design)'
    r'[^\]]*\]'
)

_SET_VAR_PATTERN = re.compile(
    r'^\s*set\s+(\w+)\s+(.+?)(?:\s*#.*)?$', re.MULTILINE
)


def parse_variables(
    text: str,
    source_label: str = "(text)",
) -> Dict[str, VariableBinding]:
    """Scan TCL text for 'set VARNAME value' assignments.

    Returns dict of variable name → VariableBinding.
    Handles brace-quoted values and simple collection assignments.
    """
    bindings: Dict[str, VariableBinding] = {}
    lines = text.splitlines()

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        m = _SET_VAR_PATTERN.match(stripped)
        if not m:
            continue

        name = m.group(1)
        raw = _clean_value(m.group(2))

        is_coll = bool(_COLLECTION_PATTERN.search(raw))
        bindings[name] = VariableBinding(
            name=name,
            raw_value=raw,
            resolved_value=raw,
            source_file=source_label,
            line_number=idx + 1,
            is_collection=is_coll,
        )

    return bindings


def _clean_value(raw: str) -> str:
    """Remove leading/trailing braces and strip whitespace."""
    raw = raw.strip()
    if raw.startswith("{") and raw.endswith("}"):
        raw = raw[1:-1]
    return raw.strip()


# ── Variable resolution ───────────────────────────────────────────────────────

def resolve_variables(
    text: str,
    symbol_table: SymbolTable,
    max_depth: int = 5,
) -> str:
    """Replace $VARNAME and ${VARNAME} references in text with resolved values.

    Iterates up to max_depth for nested variable references.
    """
    result = text
    for _ in range(max_depth):
        new_text = text
        # Replace ${VARNAME} first (more specific)
        for name, binding in sorted(
            symbol_table.variables.items(), key=lambda x: -len(x[0])
        ):
            new_text = new_text.replace(f"${{{name}}}", binding.resolved_value)
            new_text = new_text.replace(f"${name}", binding.resolved_value)
        if new_text == result:
            break
        result = new_text
    return result


# ── Source file detection ──────────────────────────────────────────────────────

_SOURCE_PATTERN = re.compile(r'^\s*source\s+["\']?([^"\'\s]+)["\']?\s*(?:#.*)?$', re.MULTILINE)


def extract_source_files(text: str) -> List[str]:
    """Find 'source filename.tcl' commands in the text.

    Returns list of filenames referenced.
    """
    return _SOURCE_PATTERN.findall(text)


# ── Build symbol table from multiple files ─────────────────────────────────────

def build_symbol_table(
    main_text: str,
    linked_files: Optional[Dict[str, str]] = None,
) -> SymbolTable:
    """Parse variables from the main text and any linked TCL files.

    Later definitions override earlier ones (TCL semantics).
    """
    table = SymbolTable()

    if linked_files:
        for filename, content in linked_files.items():
            table.source_files.append(filename)
            bindings = parse_variables(content, source_label=filename)
            table.variables.update(bindings)

    # Main text variables override linked file variables
    main_bindings = parse_variables(main_text, source_label="(main)")
    table.variables.update(main_bindings)

    # Resolve variable values (variables may reference other variables)
    for binding in table.variables.values():
        resolved = binding.raw_value
        for _ in range(5):
            new_resolved = resolved
            for name, other_binding in table.variables.items():
                new_resolved = new_resolved.replace(f"${{{name}}}", other_binding.resolved_value)
                new_resolved = new_resolved.replace(f"${name}", other_binding.resolved_value)
            if new_resolved == resolved:
                break
            resolved = new_resolved
        binding.resolved_value = resolved

    return table
