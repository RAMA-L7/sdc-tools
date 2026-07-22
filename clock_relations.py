"""
Clock Relation Analyzer
Parses clock definitions, infers correct relationships, and detects mismatches
in set_clock_groups constraints. Inspired by Ausdia's "Seemingly Simple Clock
Relations Quiz" — incorrect clock relations cause SI pessimism or masked timing paths.
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from itertools import combinations


# ── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class ClockDefCK:
    """A clock definition parsed from an SDC file."""
    name: str
    period: float
    source_port: str
    is_generated: bool = False
    master_clock: str = ""       # master clock name for generated clocks
    divide_by: int = 1
    is_virtual: bool = False
    raw_text: str = ""


@dataclass
class ClockPair:
    """Inferred relationship between two clocks."""
    clock_a: str
    clock_b: str
    inferred_relation: str       # "asynchronous" | "synchronous" | "physically_exclusive" | "logically_exclusive"
    reason: str
    confidence: float = 1.0      # 0.0–1.0


@dataclass
class ClockMismatch:
    """A mismatch between inferred and specified clock relationships."""
    code: str                    # SDC-060..063
    severity: str                # "warning" | "info"
    clock_a: str
    clock_b: str
    specified: str               # what the SDC says
    expected: str                # what it should be
    msg: str


@dataclass
class RelationAnalysisResult:
    """Full analysis result."""
    clocks: List[ClockDefCK] = field(default_factory=list)
    pairs: List[ClockPair] = field(default_factory=list)
    existing_groups: List[Dict] = field(default_factory=list)
    mismatches: List[ClockMismatch] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)


# ── Clock parsing ────────────────────────────────────────────────────────────

def parse_clocks_from_sdc(text: str) -> List[ClockDefCK]:
    """Extract all create_clock and create_generated_clock definitions."""
    clocks: List[ClockDefCK] = []

    # Primary clocks: create_clock -name NAME -period PERIOD [get_ports PORT]
    for m in re.finditer(
        r'create_clock\s+(-name\s+\S+\s+)?'
        r'(?:-period\s+([\d.]+)\s+)'
        r'(?:\[get_ports\s+(\S+)\])?'
        r'(.*)',
        text, re.MULTILINE
    ):
        name = ""
        name_m = re.search(r'-name\s+(\S+)', m.group(0))
        if name_m:
            name = name_m.group(1)
        period = float(m.group(2)) if m.group(2) else 5.0
        port = m.group(3) or ""
        extra = m.group(4) or ""
        # Skip if this is actually a generated clock line
        if 'create_generated_clock' in m.group(0):
            continue
        # Check for -add flag (multiple clocks on same port)
        has_add = '-add' in extra
        clocks.append(ClockDefCK(
            name=name,
            period=period,
            source_port=port,
            is_generated=False,
            raw_text=m.group(0).strip(),
        ))

    # Generated clocks: parse each command then extract flags individually
    for m in re.finditer(
        r'create_generated_clock\s+(.+?)(?=\n\S|\Z)',
        text, re.DOTALL
    ):
        cmd = m.group(0)
        name_m = re.search(r'-name\s+(\S+)', cmd)
        name = name_m.group(1) if name_m else ""
        div_m = re.search(r'-divide_by\s+(\d+)', cmd)
        divide_by = int(div_m.group(1)) if div_m else 1
        mul_m = re.search(r'-multiply_by\s+(\d+)', cmd)
        multiply_by = int(mul_m.group(1)) if mul_m else None
        src_m = re.search(r'-source\s+\[get_ports\s+(\S+)\]', cmd)
        port = src_m.group(1) if src_m else ""
        master_m = re.search(r'-master_clock\s+(\S+)', cmd)
        master = master_m.group(1) if master_m else ""

        # Try to find master clock period
        master_period = 5.0
        for ck in clocks:
            if ck.name == master:
                master_period = ck.period
                break

        gen_period = master_period * divide_by if divide_by > 1 else master_period
        if multiply_by and multiply_by > 0:
            gen_period = master_period / multiply_by

        clocks.append(ClockDefCK(
            name=name,
            period=gen_period,
            source_port=port,
            is_generated=True,
            master_clock=master,
            divide_by=divide_by,
            raw_text=m.group(0).strip(),
        ))

    return clocks


# ── Relation inference ───────────────────────────────────────────────────────

def infer_relation(ck_a: ClockDefCK, ck_b: ClockDefCK) -> ClockPair:
    """Determine the correct relationship between two clocks."""
    a, b = ck_a, ck_b

    # Rule 1: Parent-child (generated from same master)
    if a.is_generated and a.master_clock == b.name:
        return ClockPair(
            clock_a=a.name, clock_b=b.name,
            inferred_relation="synchronous",
            reason=f"{a.name} is derived from {b.name} (divide_by={a.divide_by}) — parent-child relationship",
        )
    if b.is_generated and b.master_clock == a.name:
        return ClockPair(
            clock_a=a.name, clock_b=b.name,
            inferred_relation="synchronous",
            reason=f"{b.name} is derived from {a.name} (divide_by={b.divide_by}) — parent-child relationship",
        )

    # Rule 2: Both generated from the same master
    if (a.is_generated and b.is_generated and
            a.master_clock and a.master_clock == b.master_clock):
        return ClockPair(
            clock_a=a.name, clock_b=b.name,
            inferred_relation="synchronous",
            reason=f"Both derived from same master clock {a.master_clock} — synchronous siblings",
        )

    # Rule 3: Same source port, different periods → physically exclusive
    if (a.source_port and b.source_port and
            a.source_port == b.source_port and
            a.period != b.period and
            not a.is_generated and not b.is_generated):
        return ClockPair(
            clock_a=a.name, clock_b=b.name,
            inferred_relation="physically_exclusive",
            reason=f"Both primary clocks on port {a.source_port} with different periods ({a.period} vs {b.period} ns) — only one active at a time",
        )

    # Rule 4: Same source port, same period → same clock (duplicate)
    if (a.source_port and b.source_port and
            a.source_port == b.source_port and
            a.period == b.period and
            not a.is_generated and not b.is_generated):
        return ClockPair(
            clock_a=a.name, clock_b=b.name,
            inferred_relation="physically_exclusive",
            reason=f"Identical primary clocks on port {a.source_port} — duplicates",
        )

    # Rule 5: Different source ports, no common master → asynchronous
    if a.source_port != b.source_port:
        # Check if they share a common ancestor
        masters_a = _get_ancestors(a, clocks=[])
        masters_b = _get_ancestors(b, clocks=[])
        common = set(masters_a) & set(masters_b)
        if common:
            return ClockPair(
                clock_a=a.name, clock_b=b.name,
                inferred_relation="synchronous",
                reason=f"Share common ancestor clock(s): {', '.join(common)}",
            )
        return ClockPair(
            clock_a=a.name, clock_b=b.name,
            inferred_relation="asynchronous",
            reason=f"Different source ports ({a.source_port or '?'} vs {b.source_port or '?'}) with no common master — no deterministic phase relationship",
        )

    # Default: asynchronous
    return ClockPair(
        clock_a=a.name, clock_b=b.name,
        inferred_relation="asynchronous",
        reason="Unable to determine a specific relationship — defaulting to asynchronous",
        confidence=0.5,
    )


def _get_ancestors(ck: ClockDefCK, clocks: List[ClockDefCK]) -> List[str]:
    """Get all ancestor clock names (master, master's master, etc.)."""
    ancestors = []
    if ck.master_clock:
        ancestors.append(ck.master_clock)
    return ancestors


# ── Existing group parsing ───────────────────────────────────────────────────

def _parse_existing_groups(text: str) -> List[Dict]:
    """Extract set_clock_groups constraints."""
    # Join line continuations (\ + newline) so multi-line commands are single lines
    cleaned = re.sub(r'\\\s*\n\s*', ' ', text)
    groups = []
    for m in re.finditer(
        r'set_clock_groups\s+'
        r'(-asynchronous|-logically_exclusive|-physically_exclusive)\s+'
        r'(.+?)(?=\n\S|\Z)',
        cleaned, re.DOTALL
    ):
        group_type = m.group(1).lstrip('-')
        body = m.group(2)

        # Extract clock group lists
        clock_groups = []
        for gm in re.finditer(r'-group\s+\[get_clocks\s+([^\]]+)\]', body):
            clock_names = [n.strip() for n in gm.group(1).split() if n.strip()]
            clock_groups.append(clock_names)

        # Generate all pairs from this constraint
        specified_pairs = set()
        if len(clock_groups) >= 2:
            for gi, gj in combinations(range(len(clock_groups)), 2):
                for ca in clock_groups[gi]:
                    for cb in clock_groups[gj]:
                        pair_key = tuple(sorted([ca, cb]))
                        specified_pairs.add((pair_key, group_type))

        groups.append({
            'type': group_type,
            'clock_groups': clock_groups,
            'pairs': specified_pairs,
            'raw': m.group(0).strip(),
        })

    return groups


# ── Mismatch detection ──────────────────────────────────────────────────────

def _find_mismatches(
    pairs: List[ClockPair],
    existing_groups: List[Dict],
) -> List[ClockMismatch]:
    """Compare inferred vs. specified relationships and find mismatches."""
    mismatches: List[ClockMismatch] = []

    # Build a lookup: (clock_a, clock_b) → specified_type
    specified: Dict[Tuple[str, str], str] = {}
    for grp in existing_groups:
        for (pair_key, grp_type) in grp['pairs']:
            specified[pair_key] = grp_type

    # Also build reverse lookup for all clocks mentioned in groups
    all_specified_clocks = set()
    for grp in existing_groups:
        for cg in grp['clock_groups']:
            all_specified_clocks.update(cg)

    for pair in pairs:
        key = tuple(sorted([pair.clock_a, pair.clock_b]))

        if key in specified:
            specified_type = specified[key]
            if specified_type != pair.inferred_relation and not (
                pair.inferred_relation == "synchronous" and specified_type == "asynchronous"
            ):
                # Synchronous marked as asynchronous is generally OK (conservative)
                # Mismatch!
                if (pair.inferred_relation == "physically_exclusive" and
                        specified_type == "asynchronous"):
                    mismatches.append(ClockMismatch(
                        code="SDC-060",
                        severity="warning",
                        clock_a=pair.clock_a, clock_b=pair.clock_b,
                        specified=f"-{specified_type}",
                        expected=f"-physically_exclusive",
                        msg=(
                            f"Clocks {pair.clock_a}/{pair.clock_b} marked -asynchronous but "
                            f"should be -physically_exclusive: {pair.reason}. "
                            f"Using -asynchronous causes unnecessary Crosstalk/SI analysis on paths that can never exist."
                        ),
                    ))
                elif (pair.inferred_relation == "synchronous" and
                      specified_type in ("logically_exclusive", "physically_exclusive")):
                    mismatches.append(ClockMismatch(
                        code="SDC-061",
                        severity="warning",
                        clock_a=pair.clock_a, clock_b=pair.clock_b,
                        specified=f"-{specified_type}",
                        expected="synchronous (no exclusion needed)",
                        msg=(
                            f"Clocks {pair.clock_a}/{pair.clock_b} marked -{specified_type} but "
                            f"are actually synchronous: {pair.reason}. "
                            f"This masks real timing paths and leaves setup/hold un-optimized."
                        ),
                    ))
                elif (pair.inferred_relation == "asynchronous" and
                      specified_type in ("logically_exclusive", "physically_exclusive")):
                    mismatches.append(ClockMismatch(
                        code="SDC-063",
                        severity="info",
                        clock_a=pair.clock_a, clock_b=pair.clock_b,
                        specified=f"-{specified_type}",
                        expected=f"-asynchronous",
                        msg=(
                            f"Clocks {pair.clock_a}/{pair.clock_b} marked -{specified_type} but "
                            f"appear to be asynchronous: {pair.reason}. "
                            f"Verify this is intentional."
                        ),
                    ))
        else:
            # No constraint specified for this pair
            # Synchronous pairs don't need set_clock_groups — skip
            if pair.inferred_relation == "synchronous":
                continue
            if pair.inferred_relation in ("asynchronous", "physically_exclusive"):
                mismatches.append(ClockMismatch(
                    code="SDC-062",
                    severity="info",
                    clock_a=pair.clock_a, clock_b=pair.clock_b,
                    specified="(none)",
                    expected=f"-{pair.inferred_relation}",
                    msg=(
                        f"No set_clock_groups for {pair.clock_a}/{pair.clock_b}. "
                        f"Inferred: {pair.inferred_relation}. {pair.reason}."
                    ),
                ))

    return mismatches


# ── Main entry point ─────────────────────────────────────────────────────────

def analyze_clock_relations(text: str) -> RelationAnalysisResult:
    """Analyze all clock relations in an SDC file.

    1. Parse all clock definitions
    2. Infer correct relationship for every pair
    3. Parse existing set_clock_groups constraints
    4. Detect mismatches and missing constraints
    """
    clocks = parse_clocks_from_sdc(text)
    existing_groups = _parse_existing_groups(text)

    # Generate all pairs
    pairs: List[ClockPair] = []
    for ca, cb in combinations(clocks, 2):
        pairs.append(infer_relation(ca, cb))

    # Find mismatches
    mismatches = _find_mismatches(pairs, existing_groups)

    # Stats
    n_sync = sum(1 for p in pairs if p.inferred_relation == "synchronous")
    n_async = sum(1 for p in pairs if p.inferred_relation == "asynchronous")
    n_phy = sum(1 for p in pairs if p.inferred_relation == "physically_exclusive")
    n_log = sum(1 for p in pairs if p.inferred_relation == "logically_exclusive")
    n_mismatch = sum(1 for m in mismatches if m.severity == "warning")
    n_missing = sum(1 for m in mismatches if m.severity == "info")

    stats = {
        "clocks": len(clocks),
        "pairs": len(pairs),
        "synchronous": n_sync,
        "asynchronous": n_async,
        "physically_exclusive": n_phy,
        "logically_exclusive": n_log,
        "mismatches": n_mismatch,
        "missing": n_missing,
        "constraints": len(existing_groups),
    }

    return RelationAnalysisResult(
        clocks=clocks,
        pairs=pairs,
        existing_groups=existing_groups,
        mismatches=mismatches,
        stats=stats,
    )
