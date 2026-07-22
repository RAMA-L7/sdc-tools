"""
Wildcard Pattern Analyzer for SDC files
Parse, compare, and risk-score wildcard patterns found in SDC object specifications.
"""

import re
import difflib
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class WildcardPattern:
    raw: str                      # original pattern text
    pattern_type: str = "unknown" # "pin" | "port" | "cell" | "clock" | "net"
    has_wildcards: bool = False   # True if contains *, ?, [...]
    specificity: str = "exact"    # "broad" | "moderate" | "specific" | "exact"
    risk_score: int = 0           # 0-10, higher = more risk


@dataclass
class WildcardComparison:
    v1_pattern: WildcardPattern
    v2_pattern: WildcardPattern
    command_type: str             # "set_false_path", "set_multicycle_path", etc.
    change_type: str              # "narrowed" | "broadened" | "same" | "rewritten"
    risk_explanation: str = ""


# ── Pattern parsing ───────────────────────────────────────────────────────────

# Context keywords for identifying object type
_TYPE_KEYWORDS = {
    "get_pins": "pin",
    "get_ports": "port",
    "get_cells": "cell",
    "get_clocks": "clock",
    "get_nets": "net",
    "all_inputs": "port",
    "all_outputs": "port",
    "all_clocks": "clock",
    "all_registers": "cell",
    "all_nets": "net",
}

_BROAD_PATTERNS = re.compile(r'\[\s*all_(?:pins|cells|nets|inputs|outputs|registers)\s*\]')


def parse_wildcard(text: str) -> WildcardPattern:
    """Analyze a wildcard pattern from an SDC object specification.

    Returns a WildcardPattern with specificity classification and risk score.
    """
    raw = text.strip()
    pattern_type = _infer_type(raw)
    has_wildcards = bool(re.search(r'[\*\?\[]', raw))
    specificity = _classify_specificity(raw, has_wildcards)
    risk_score = _compute_risk(raw, pattern_type, specificity)

    return WildcardPattern(
        raw=raw,
        pattern_type=pattern_type,
        has_wildcards=has_wildcards,
        specificity=specificity,
        risk_score=risk_score,
    )


def _infer_type(text: str) -> str:
    """Infer object type from TCL collection command context."""
    for keyword, ptype in _TYPE_KEYWORDS.items():
        if keyword in text:
            return ptype
    return "unknown"


def _classify_specificity(text: str, has_wildcards: bool) -> str:
    """Classify how specific a wildcard pattern is."""
    if not has_wildcards and not _BROAD_PATTERNS.search(text):
        return "exact"

    if _BROAD_PATTERNS.search(text):
        return "broad"

    if re.search(r'\[\s*\*\s*\]', text):
        return "broad"

    # Count * and ? characters
    star_count = text.count("*")
    qmark_count = text.count("?")

    if star_count >= 2:
        return "moderate"
    if star_count == 1 and qmark_count == 0:
        return "specific"
    if qmark_count > 0:
        return "moderate"

    return "moderate"


def _compute_risk(text: str, pattern_type: str, specificity: str) -> int:
    """Compute risk score 0-10 based on how broad/risky a pattern is."""
    if _BROAD_PATTERNS.search(text):
        return 9

    if re.search(r'\[\s*\*\s*\]', text):
        return 8

    if specificity == "broad":
        return 8
    if specificity == "moderate":
        return 4
    if specificity == "specific":
        return 2
    return 0


# ── Wildcard comparison ───────────────────────────────────────────────────────

def compare_wildcards(
    v1_text: str,
    v2_text: str,
    command_type: str = "",
) -> WildcardComparison:
    """Compare two wildcard patterns and classify the change.

    Detects if the pattern was narrowed, broadened, rewritten, or unchanged.
    """
    v1 = parse_wildcard(v1_text)
    v2 = parse_wildcard(v2_text)

    if v1_text == v2_text:
        return WildcardComparison(
            v1_pattern=v1,
            v2_pattern=v2,
            command_type=command_type,
            change_type="same",
            risk_explanation="No change in wildcard pattern.",
        )

    # Use difflib to check similarity
    similarity = difflib.SequenceMatcher(None, v1_text, v2_text).ratio()

    # Determine if narrowed or broadened based on pattern characteristics
    v1_stars = v1_text.count("*")
    v2_stars = v2_text.count("*")
    v1_chars = len(v1_text)
    v2_chars = len(v2_text)

    # More specific == narrower scope (fewer objects matched)
    narrowed = (v2_stars < v1_stars) or (v2_chars > v1_chars and "*" in v1_text)
    broadened = (v2_stars > v1_stars) or (v2_chars < v1_chars)

    explanation_parts = []
    if narrowed and not broadened:
        change_type = "narrowed"
        explanation_parts.append("Pattern scope narrowed — fewer objects will match.")
    elif broadened and not narrowed:
        change_type = "broadened"
        explanation_parts.append("Pattern scope broadened — more objects will match.")
    else:
        change_type = "rewritten"
        explanation_parts.append("Pattern was rewritten — may affect different objects.")

    if similarity < 0.7:
        explanation_parts.append(f"Low similarity ({similarity:.0%}) between old and new pattern.")

    return WildcardComparison(
        v1_pattern=v1,
        v2_pattern=v2,
        command_type=command_type,
        change_type=change_type,
        risk_explanation=" ".join(explanation_parts),
    )


# ── Broad pattern flagging ────────────────────────────────────────────────────

def flag_overly_broad(patterns: List[str]) -> List[WildcardPattern]:
    """Return wildcard patterns with risk_score >= 7."""
    flagged = []
    for p in patterns:
        wc = parse_wildcard(p)
        if wc.risk_score >= 7:
            flagged.append(wc)
    return flagged
